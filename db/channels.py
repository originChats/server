import copy
import json
import os
import threading
from typing import Dict, List, Optional
from . import users
import emoji

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
channels_db_dir = os.path.join(_MODULE_DIR, "channels")
channels_index = os.path.join(_MODULE_DIR, "channels.json")
DEFAULT_CHANNELS = [
    {
        "type": "text",
        "name": "general",
        "description": "General chat channel for everyone",
        "permissions": {
            "view": ["user"],
            "send": ["user"],
            "delete": ["admin", "moderator"]
        }
    }
]

_lock = threading.RLock()

_channels_cache: List[dict] = []
_channels_loaded: bool = False


def _load_channels_index() -> List[dict]:
    global _channels_cache, _channels_loaded
    try:
        with open(channels_index, 'r') as f:
            _channels_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _channels_cache = copy.deepcopy(DEFAULT_CHANNELS)
    _channels_loaded = True
    return _channels_cache


def _save_channels_index(channels: List[dict]) -> None:
    global _channels_cache, _channels_loaded
    tmp = channels_index + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(channels, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, channels_index)
    _channels_cache = channels
    _channels_loaded = True


def _get_channels_cache() -> List[dict]:
    if not _channels_loaded:
        _load_channels_index()
    return _channels_cache


_msg_cache: Dict[str, dict] = {}


def _build_id_index(messages):
    return {msg["id"]: i for i, msg in enumerate(messages) if "id" in msg}


def _load_channel_into_cache(channel_name):
    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    messages = []
    offsets = []
    lengths = []

    try:
        with open(channel_file, 'rb') as f:
            raw = f.read()
    except FileNotFoundError:
        _msg_cache[channel_name] = {
            "messages": [],
            "id_to_idx": {},
            "offsets": [],
            "lengths": [],
        }
        return _msg_cache[channel_name]

    if not raw.strip():
        _msg_cache[channel_name] = {
            "messages": [],
            "id_to_idx": {},
            "offsets": [],
            "lengths": [],
        }
        return _msg_cache[channel_name]

    stripped = raw.lstrip()
    if stripped.startswith(b'['):
        try:
            messages = json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError:
            messages = []
        entry = {
            "messages": messages,
            "id_to_idx": _build_id_index(messages),
            "offsets": None,
            "lengths": None,
        }
        _msg_cache[channel_name] = entry
        _full_rewrite(channel_name)
        return _msg_cache[channel_name]

    pos = 0
    for line_bytes in raw.split(b'\n'):
        content_bytes = line_bytes.rstrip(b'\r')
        line_str = content_bytes.decode('utf-8').strip()
        if line_str:
            try:
                msg = json.loads(line_str)
                messages.append(msg)
                offsets.append(pos)
                lengths.append(len(content_bytes))
            except json.JSONDecodeError:
                pass
        pos += len(line_bytes) + 1

    _msg_cache[channel_name] = {
        "messages": messages,
        "id_to_idx": _build_id_index(messages),
        "offsets": offsets,
        "lengths": lengths,
    }
    return _msg_cache[channel_name]


def _get_channel_cache(channel_name):
    if channel_name not in _msg_cache:
        _load_channel_into_cache(channel_name)
    return _msg_cache[channel_name]


def _full_rewrite(channel_name):
    cache = _msg_cache.get(channel_name)
    if cache is None:
        return

    messages = cache["messages"]
    os.makedirs(channels_db_dir, exist_ok=True)
    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    tmp = channel_file + ".tmp"

    lines = [json.dumps(msg, separators=(',', ':'), ensure_ascii=False) for msg in messages]
    encoded_lines = [line.encode('utf-8') for line in lines]
    content_bytes = b'\n'.join(encoded_lines)

    with open(tmp, 'wb') as f:
        f.write(content_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, channel_file)

    offsets = []
    lengths = []
    pos = 0
    for lb in encoded_lines:
        offsets.append(pos)
        lengths.append(len(lb))
        pos += len(lb) + 1

    cache["offsets"] = offsets
    cache["lengths"] = lengths


def _rebuild_offsets(channel_name):
    cache = _msg_cache.get(channel_name)
    if cache is None:
        return

    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    offsets = []
    lengths = []
    try:
        with open(channel_file, 'rb') as f:
            raw = f.read()
    except OSError:
        return

    pos = 0
    for line_bytes in raw.split(b'\n'):
        content_bytes = line_bytes.rstrip(b'\r')
        if content_bytes.strip():
            offsets.append(pos)
            lengths.append(len(content_bytes))
        pos += len(line_bytes) + 1

    cache["offsets"] = offsets
    cache["lengths"] = lengths


def _patch_line_in_place(channel_name, idx, new_serialised):
    cache = _msg_cache.get(channel_name)
    if cache is None or cache["offsets"] is None:
        return False

    offsets = cache["offsets"]
    lengths = cache["lengths"]

    if idx >= len(offsets):
        return False

    new_bytes = new_serialised.encode('utf-8')
    orig_len = lengths[idx]

    if len(new_bytes) > orig_len:
        return False

    padding = orig_len - len(new_bytes)
    if padding > 0:
        new_bytes = new_bytes + b' ' * padding

    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    try:
        with open(channel_file, 'r+b') as f:
            f.seek(offsets[idx])
            f.write(new_bytes)
            f.flush()
            os.fsync(f.fileno())
        return True
    except OSError:
        return False


def _read_channel_file(channel_name):
    return list(_get_channel_cache(channel_name)["messages"])


def _write_channel_file(channel_name, messages):
    with _lock:
        cache = _get_channel_cache(channel_name)
        old_messages = cache["messages"]
        old_id_to_idx = cache["id_to_idx"]
        cache["messages"] = messages
        cache["id_to_idx"] = _build_id_index(messages)
        try:
            _full_rewrite(channel_name)
        except Exception:
            cache["messages"] = old_messages
            cache["id_to_idx"] = old_id_to_idx
            raise


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    os.makedirs(channels_db_dir, exist_ok=True)

    if not os.path.exists(channels_index):
        tmp = channels_index + ".tmp"
        with open(tmp, 'w') as f:
            json.dump(DEFAULT_CHANNELS, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, channels_index)

    channels = _get_channels_cache()

    for channel in channels:
        if channel.get("type") not in ["text", "voice"]:
            continue
        channel_name = channel.get("name")
        if not channel_name:
            continue
        channel_file = os.path.join(channels_db_dir, channel_name + ".json")
        if not os.path.exists(channel_file):
            tmp = channel_file + ".tmp"
            with open(tmp, 'wb') as f:
                pass
            os.replace(tmp, channel_file)


_ensure_storage()


def get_channel(channel_name):
    """
    Get channel data by channel name.
    """
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                return copy.deepcopy(channel)
        return None


def get_channel_messages(channel_name, start, limit):
    """
    Retrieve messages from a specific channel.

    Args:
        channel_name (str): The name of the channel to retrieve messages from.
        start (int or str, optional): If int, the number of recent messages to skip (offset from the end).
        If str, the message ID to retrieve messages before (older messages than the specified ID).
        Defaults to 0.
        limit (int, optional): The maximum number of messages to retrieve. Defaults to 100.

    Returns:
        list: A list of messages from the specified channel, in chronological order (oldest first).
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        channel_data = cache["messages"]

        if not channel_data:
            return []

        if not limit:
            limit = 100
        if limit > 200:
            limit = 200

        if isinstance(start, int):
            if start < 0:
                start = 0
            end = len(channel_data) - start
            begin = max(0, end - limit)
        else:
            idx = cache["id_to_idx"].get(start)
            if idx is None:
                return []
            end = idx
            begin = max(0, end - limit)

        channel_data_len = len(channel_data)
        if begin > channel_data_len:
            return []
        end = min(end, channel_data_len)
        begin = max(begin, 0)
        end = max(end, 0)

        if begin == end:
            return []

        return list(channel_data[begin:end])


def convert_messages_to_user_format(messages):
    """
    Convert messages with user IDs to messages with usernames for sending to clients.
    This ensures clients never see user IDs, only usernames.
    """
    user_ids_needed = set()
    for msg in messages:
        if "user" in msg:
            user_ids_needed.add(msg["user"])
        if "reply_to" in msg and "user" in msg["reply_to"]:
            user_ids_needed.add(msg["reply_to"]["user"])
        if "reactions" in msg:
            for uid_list in msg["reactions"].values():
                user_ids_needed.update(uid_list)

    uid_to_name = {uid: users.get_username_by_id(uid) for uid in user_ids_needed}

    converted = []
    for msg in messages:
        msg_copy = msg.copy()

        if "user" in msg_copy:
            uid = msg_copy["user"]
            msg_copy["user"] = uid_to_name.get(uid) or uid

        if "reply_to" in msg_copy and "user" in msg_copy["reply_to"]:
            msg_copy["reply_to"] = msg_copy["reply_to"].copy()
            uid = msg_copy["reply_to"]["user"]
            msg_copy["reply_to"]["user"] = uid_to_name.get(uid) or uid

        if "reactions" in msg_copy:
            converted_reactions = {}
            for emo, uid_list in msg_copy["reactions"].items():
                converted_reactions[emo] = [uid_to_name.get(u) or u for u in uid_list]
            msg_copy["reactions"] = converted_reactions

        converted.append(msg_copy)

    return converted


def save_channel_message(channel_name, message):
    """
    Save a message to a specific channel using append operation.
    Ultra-fast: just appends one line to the file.

    Args:
        channel_name (str): The name of the channel to save the message to.
        message (dict): The message to save, should contain 'user', 'content', and 'timestamp'.

    Returns:
        bool: True if the message was saved successfully, False otherwise.
    """
    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    os.makedirs(channels_db_dir, exist_ok=True)

    with _lock:
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]

        serialised = json.dumps(message, separators=(',', ':'), ensure_ascii=False)
        serialised_bytes = serialised.encode('utf-8')

        try:
            with open(channel_file, 'rb') as f:
                first_byte = f.read(1)
        except FileNotFoundError:
            first_byte = None

        if first_byte == b'[':
            messages.append(message)
            cache["id_to_idx"][message["id"]] = len(messages) - 1
            try:
                _full_rewrite(channel_name)
            except Exception:
                messages.pop()
                cache["id_to_idx"].pop(message["id"], None)
                raise
        elif first_byte is not None:
            new_offset: Optional[int] = None
            if cache["offsets"] is not None:
                if messages:
                    new_offset = cache["offsets"][-1] + cache["lengths"][-1] + 1
                else:
                    new_offset = 0

            prefix = b'\n' if messages else b''
            with open(channel_file, 'ab') as f:
                f.write(prefix + serialised_bytes)
                f.flush()
                os.fsync(f.fileno())

            idx = len(messages)
            messages.append(message)
            cache["id_to_idx"][message["id"]] = idx
            if cache["offsets"] is not None and new_offset is not None:
                cache["offsets"].append(new_offset)
                cache["lengths"].append(len(serialised_bytes))
            elif cache["offsets"] is None:
                _rebuild_offsets(channel_name)
        else:
            tmp = channel_file + ".tmp"
            with open(tmp, 'wb') as f:
                f.write(serialised_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, channel_file)

            messages.append(message)
            cache["id_to_idx"][message["id"]] = 0
            if cache["offsets"] is not None:
                cache["offsets"] = [0]
                cache["lengths"] = [len(serialised_bytes)]

    return True


def get_all_channels_for_roles(roles):
    """
    Get all channels available for the specified roles.

    Args:
        roles (list): A list of roles to filter channels by.

    Returns:
        list: A list of channel info dicts available for the specified roles.
    """
    with _lock:
        channels = []
        for channel in _get_channels_cache():
            permissions = channel.get("permissions", {})
            view_roles = permissions.get("view", [])
            if any(role in view_roles for role in roles):
                channels.append(copy.deepcopy(channel))
        return channels


def edit_channel_message(channel_name, message_id, new_content):
    """
    Edit a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to edit.
        new_content (str): The new content for the message.

    Returns:
        bool: True if the message was edited successfully, False otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        id_to_idx = cache["id_to_idx"]

        if message_id not in id_to_idx:
            return False

        idx = id_to_idx[message_id]
        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        msg["content"] = new_content
        msg["edited"] = True

        new_serialised = json.dumps(msg, separators=(',', ':'), ensure_ascii=False)

        if _patch_line_in_place(channel_name, idx, new_serialised):
            cache["messages"][idx] = msg
        else:
            cache["messages"][idx] = msg
            try:
                _full_rewrite(channel_name)
            except Exception:
                cache["messages"][idx] = old_msg
                raise

        return True


def get_channel_message(channel_name, message_id):
    """
    Retrieve a specific message from a channel by its ID.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to retrieve.

    Returns:
        dict: The message if found, None otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return None
        msg = copy.deepcopy(cache["messages"][idx])
        msg["position"] = idx + 1
        return msg


def does_user_have_permission(channel_name, user_roles, permission_type):
    """
    Check if a user with specific roles has permission to perform an action on a channel.

    Args:
        channel_name (str): The name of the channel.
        user_roles (list): A list of roles assigned to the user.
        permission_type (str): The type of permission to check (e.g., "view", "edit_own").

    Returns:
        bool: True if the user has the required permission, False otherwise.
    """
    if "owner" in user_roles:
        return True
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                allowed_roles = permissions.get(permission_type, [])
                return any(role in allowed_roles for role in user_roles)
    return False


def delete_channel_message(channel_name, message_id):
    """
    Delete a message from a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to delete.

    Returns:
        bool: True if the message was deleted successfully, False otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)

        if message_id not in cache["id_to_idx"]:
            return True

        new_messages = [m for m in cache["messages"] if m.get("id") != message_id]
        old_messages = cache["messages"]
        old_id_to_idx = cache["id_to_idx"]

        cache["messages"] = new_messages
        cache["id_to_idx"] = _build_id_index(new_messages)
        try:
            _full_rewrite(channel_name)
        except Exception:
            cache["messages"] = old_messages
            cache["id_to_idx"] = old_id_to_idx
            raise

    return True


def get_channels():
    """
    Get all channels from the channels index.

    Returns:
        list: A list of channel info dicts.
    """
    with _lock:
        return copy.deepcopy(_get_channels_cache())


def create_channel(channel_name, channel_type, description=None, wallpaper=None, permissions=None, size=None):
    """
    Create a new channel.

    Args:
        channel_name (str): The name of the channel to create.
        channel_type (str): The type of the channel (e.g., "text", "voice", "separator").
        description (str, optional): Channel description.
        wallpaper (str, optional): Wallpaper URL.
        permissions (dict, optional): Channel permissions.
        size (int, optional): Size for separator channels.

    Returns:
        bool: True if the channel was created successfully, False if it already exists.
    """
    with _lock:
        channels = copy.deepcopy(_get_channels_cache())

        if any(channel.get('name') == channel_name for channel in channels):
            return False

        new_channel = {
            "name": channel_name,
            "type": channel_type
        }

        if channel_type != "separator":
            new_channel["permissions"] = permissions or {
                "view": ["owner"],
                "send": ["owner"]
            }

        if description:
            new_channel["description"] = description
        if wallpaper:
            new_channel["wallpaper"] = wallpaper
        if size and channel_type == "separator":
            new_channel["size"] = size

        channels.append(new_channel)

        if channel_type in ["text", "voice"]:
            os.makedirs(channels_db_dir, exist_ok=True)
            channel_file = os.path.join(channels_db_dir, channel_name + ".json")
            tmp = channel_file + ".tmp"
            with open(tmp, 'wb') as f:
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, channel_file)

        _save_channels_index(channels)

    return True


def can_user_pin(channel_name, user_roles):
    """
    Check if a user with specific roles can pin messages in a channel.
    If the channel does not specify pin, only owner is allowed by default
    """
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "pin" not in permissions:
                    return "owner" in user_roles
                allowed_roles = permissions.get("pin", [])
                return any(role in allowed_roles for role in user_roles)
    return False


def pin_channel_message(channel_name, message_id):
    """
    Pin a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to pin.

    Returns:
        bool: True if the message was pinned successfully, False otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return False

        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        msg["pinned"] = True

        new_serialised = json.dumps(msg, separators=(',', ':'), ensure_ascii=False)
        if _patch_line_in_place(channel_name, idx, new_serialised):
            cache["messages"][idx] = msg
        else:
            cache["messages"][idx] = msg
            try:
                _full_rewrite(channel_name)
            except Exception:
                cache["messages"][idx] = old_msg
                raise

    return True


def unpin_channel_message(channel_name, message_id):
    """
    Unpin a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to unpin.

    Returns:
        bool: True if the message was unpinned successfully, False otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return False

        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        msg["pinned"] = False

        new_serialised = json.dumps(msg, separators=(',', ':'), ensure_ascii=False)
        if _patch_line_in_place(channel_name, idx, new_serialised):
            cache["messages"][idx] = msg
        else:
            cache["messages"][idx] = msg
            try:
                _full_rewrite(channel_name)
            except Exception:
                cache["messages"][idx] = old_msg
                raise

    return True


def get_pinned_messages(channel_name):
    """
    Get the pinned messages in a specific channel.

    Args:
        channel_name (str): The name of the channel.

    Returns:
        list: A list of all pinned messages in a channel
    """
    with _lock:
        messages = _get_channel_cache(channel_name)["messages"]
        pinned = [copy.deepcopy(msg) for msg in messages if msg.get("pinned")]
    return list(reversed(pinned))


def search_channel_messages(channel_name, query):
    """
    Search for messages in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        query (str): The search query.

    Returns:
        list: A list of messages that match the search query.
    """
    with _lock:
        messages = _get_channel_cache(channel_name)["messages"]
        results = [copy.deepcopy(msg) for msg in messages if query in msg.get("content", "").lower()]
    return list(reversed(results))


def delete_channel(channel_name):
    """
    Delete a channel.

    Args:
        channel_name (str): The name of the channel to delete.

    Returns:
        bool: True if the channel was deleted successfully, False if it does not exist.
    """
    with _lock:
        channels = copy.deepcopy(_get_channels_cache())
        new_channels = [ch for ch in channels if ch.get('name') != channel_name]

        if len(new_channels) == len(channels):
            return False

        _save_channels_index(new_channels)
        _msg_cache.pop(channel_name, None)

    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    try:
        os.remove(channel_file)
    except OSError:
        pass

    return True


def set_channel_permissions(channel_name, role, permission, allow=True):
    """
    Set permissions for a specific role on a channel.

    Args:
        channel_name (str): The name of the channel.
        role (str): The role to set permissions for.
        permission (str): The permission to set (e.g., "view", "edit_own", "send").

    Returns:
        bool: True if permissions were set successfully, False if the channel does not exist.
    """
    with _lock:
        channels = copy.deepcopy(_get_channels_cache())

        for channel in channels:
            if channel.get('name') == channel_name:
                if permission not in channel['permissions']:
                    channel['permissions'][permission] = []
                if allow:
                    if role not in channel['permissions'][permission]:
                        channel['permissions'][permission].append(role)
                else:
                    if role in channel['permissions'][permission]:
                        channel['permissions'][permission].remove(role)

                _save_channels_index(channels)
                return True

    return False


def get_channel_permissions(channel_name):
    """
    Get permissions for a specific channel.

    Args:
        channel_name (str): The name of the channel.

    Returns:
        dict: A dictionary of permissions for the channel, or None if the channel does not exist.
    """
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                return copy.deepcopy(channel.get("permissions", {}))
    return None


def reorder_channel(channel_name, new_position):
    """
    Reorder a channel in the channels index.

    Args:
        channel_name (str): The name of the channel to reorder.
        new_position (int): The new position for the channel (0-based index).

    Returns:
        bool: True if the channel was reordered successfully, False if it does not exist.
    """
    with _lock:
        channels = copy.deepcopy(_get_channels_cache())

        for i, channel in enumerate(channels):
            if channel.get('name') == channel_name:
                channels.pop(i)
                channels.insert(int(new_position), channel)
                _save_channels_index(channels)
                return True

    return False


def get_message_replies(channel_name, message_id, limit=50):
    """
    Get all replies to a specific message.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to get replies for.
        limit (int): Maximum number of replies to return.

    Returns:
        list: A list of messages that are replies to the specified message.
    """
    with _lock:
        messages = _get_channel_cache(channel_name)["messages"]
        replies = []
        for msg in messages:
            if msg.get("reply_to", {}).get("id") == message_id:
                replies.append(copy.deepcopy(msg))
                if len(replies) >= limit:
                    break
    return replies

def purge_messages(channel_name, count):
    """
    Purge the last 'count' messages from a channel.

    Args:
        channel_name (str): The name of the channel.
        count (int): The number of messages to purge.

    Returns:
        bool: True if messages were purged successfully, False if the channel does not exist or has fewer messages.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]

        if len(messages) < count:
            return False

        new_messages = messages[:-count]
        old_messages = cache["messages"]
        old_id_to_idx = cache["id_to_idx"]

        cache["messages"] = new_messages
        cache["id_to_idx"] = _build_id_index(new_messages)
        try:
            _full_rewrite(channel_name)
        except Exception:
            cache["messages"] = old_messages
            cache["id_to_idx"] = old_id_to_idx
            raise

    return True

def can_user_delete_own(channel_name, user_roles):
    """
    Check if a user with specific roles can delete their own message in a channel.
    If the channel does not specify delete_own, all roles are allowed by default.
    """
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "delete_own" not in permissions:
                    return True
                allowed_roles = permissions.get("delete_own", [])
                return any(role in allowed_roles for role in user_roles)
    return True


def can_user_edit_own(channel_name, user_roles):
    """
    Check if a user with specific roles can edit their own message in a channel.
    If the channel does not specify edit_own, all roles are allowed by default.
    """
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "edit_own" not in permissions:
                    return True
                allowed_roles = permissions.get("edit_own", [])
                return any(role in allowed_roles for role in user_roles)
    return False

def can_user_react(channel_name, user_roles):
    """
    Check if a user with specific roles can react to messages in a channel.
    If the channel does not specify react, all roles are allowed by default.
    """
    with _lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "react" not in permissions:
                    return True
                allowed_roles = permissions.get("react", [])
                return any(role in allowed_roles for role in user_roles)
    return False


def add_reaction(channel_name, message_id, emoji_str, user_id):
    """
    Add a reaction to a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to add the reaction to.
        emoji_str (str): The emoji to add.
        user_id (str): The ID of the user to add the reaction for.

    Returns:
        bool: True if the reaction was added successfully, False otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return False

        if not emoji.is_emoji(emoji_str):
            return False

        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        msg.setdefault("reactions", {})
        msg["reactions"].setdefault(emoji_str, [])

        if user_id in msg["reactions"][emoji_str]:
            return True

        msg["reactions"][emoji_str].append(user_id)

        new_serialised = json.dumps(msg, separators=(',', ':'), ensure_ascii=False)
        if _patch_line_in_place(channel_name, idx, new_serialised):
            cache["messages"][idx] = msg
        else:
            cache["messages"][idx] = msg
            try:
                _full_rewrite(channel_name)
            except Exception:
                cache["messages"][idx] = old_msg
                raise

    return True


def remove_reaction(channel_name, message_id, emoji_str, user_id):
    """
    Remove a reaction from a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to remove the reaction from.
        emoji_str (str): The emoji to remove.
        user_id (str): The ID of the user to remove the reaction for.

    Returns:
        bool: True if the reaction was removed successfully, False otherwise.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return False

        if not emoji.is_emoji(emoji_str):
            return False

        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        reactions = msg.get("reactions", {})
        if emoji_str not in reactions:
            return False
        if user_id not in reactions[emoji_str]:
            return False

        reactions[emoji_str].remove(user_id)
        if not reactions[emoji_str]:
            del reactions[emoji_str]
        if not reactions:
            msg.pop("reactions", None)

        new_serialised = json.dumps(msg, separators=(',', ':'), ensure_ascii=False)
        if _patch_line_in_place(channel_name, idx, new_serialised):
            cache["messages"][idx] = msg
        else:
            cache["messages"][idx] = msg
            try:
                _full_rewrite(channel_name)
            except Exception:
                cache["messages"][idx] = old_msg
                raise

    return True


def get_reactions(channel_name, message_id):
    """
    Get the reactions for a specific message in a channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to get the reactions for.

    Returns:
        dict: A dictionary containing the reactions for the message, or None if the message or channel does not exist.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return None
        return copy.deepcopy(cache["messages"][idx].get("reactions", {}))


def get_reaction_users(channel_name, message_id, emoji_str):
    """
    Get the users who reacted with a specific emoji to a specific message in a channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to get the reactions for.
        emoji (str): The emoji to get the users for.

    Returns:
        list: A list of usernames who reacted with the specified emoji, or None if the message or channel does not exist.
    """
    with _lock:
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return None
        msg = cache["messages"][idx]
        reactions = msg.get("reactions", {})
        if emoji_str in reactions:
            return list(reactions[emoji_str])
        return None


def channel_exists(channel_name):
    """
    Check if a channel exists in the channels index.

    Args:
        channel_name (str): The name of the channel to check.

    Returns:
        bool: True if the channel exists, False otherwise.
    """
    with _lock:
        return any(ch.get('name') == channel_name for ch in _get_channels_cache())


def update_channel(channel_name, updates):
    """
    Update a channel's properties. Can rename the channel if 'name' is in updates.

    Args:
        channel_name (str): The current name of the channel to update.
        updates (dict): The updates to apply. Can include:
            - name (str): New channel name (optional)
            - type (str): Channel type (optional)
            - description (str): Channel description (optional)
            - permissions (dict): Channel permissions (optional)
            - wallpaper (str): Wallpaper URL (optional)
            - size (int): Separator size (optional, for separator type)

    Returns:
        bool: True if the channel was updated successfully, False if it does not exist.
    """
    with _lock:
        channels = copy.deepcopy(_get_channels_cache())

        for channel in channels:
            if channel.get('name') == channel_name:
                old_name = channel_name

                for key, value in updates.items():
                    if key in ['name', 'type', 'description', 'permissions', 'wallpaper', 'size']:
                        channel[key] = value

                new_name = channel.get('name', old_name)

                if new_name != old_name and channel.get('type') != 'separator':
                    old_file_path = os.path.join(channels_db_dir, old_name + ".json")
                    new_file_path = os.path.join(channels_db_dir, new_name + ".json")

                    _save_channels_index(channels)

                    if os.path.exists(old_file_path):
                        os.replace(old_file_path, new_file_path)
                    if old_name in _msg_cache:
                        _msg_cache[new_name] = _msg_cache.pop(old_name)
                else:
                    _save_channels_index(channels)

                return True

    return False
