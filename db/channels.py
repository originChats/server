import copy
import json
import os
import threading
from typing import Dict, List, Optional, Tuple

from . import users
from .shared import convert_messages_to_user_format
from .storage_utils import (
    find_line_number_grep,
    count_lines_wc,
    read_lines_range,
    get_messages_around_from_file,
    build_id_index,
    atomic_write_json,
)

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
channels_db_dir = os.path.join(_MODULE_DIR, "channels")
channels_index = os.path.join(_MODULE_DIR, "channels.json")

MESSAGE_PADDING_SIZE = 512

DEFAULT_PERMISSIONS = {
    "view": ["owner"],
    "send": ["owner"],
    "delete": ["owner"],
    "delete_own": ["user"],
    "edit_own": ["user"],
    "react": ["user"],
    "pin": ["owner"],
    "create_thread": ["owner"],
}


def _normalize_permissions(permissions: dict) -> dict:
    if not permissions:
        return {}
    return {k: v for k, v in permissions.items() if v}


DEFAULT_CHANNELS = [
    {
        "type": "text",
        "name": "general",
        "description": "General chat channel for everyone",
        "permissions": {
            "view": ["user"],
            "send": ["user"],
            "delete": ["admin", "moderator"],
            "create_thread": ["user"],
        },
    }
]

_global_lock = threading.RLock()
_channel_locks: Dict[str, threading.RLock] = {}
_permission_cache: Dict[str, dict] = {}
_permission_cache_valid: bool = False


def _get_channel_lock(channel_name: str) -> threading.RLock:
    if channel_name not in _channel_locks:
        with _global_lock:
            if channel_name not in _channel_locks:
                _channel_locks[channel_name] = threading.RLock()
    return _channel_locks[channel_name]


def _invalidate_permission_cache():
    global _permission_cache_valid
    _permission_cache_valid = False


def _get_channel_permissions_cached(channel_name: str) -> Optional[dict]:
    global _permission_cache, _permission_cache_valid
    if not _permission_cache_valid:
        with _global_lock:
            _permission_cache = {
                ch["name"]: ch.get("permissions", {})
                for ch in _get_channels_cache()
                if ch.get("name")
            }
            _permission_cache_valid = True
    return _permission_cache.get(channel_name)


_channels_cache: List[dict] = []
_channels_loaded: bool = False


def _load_channels_index() -> List[dict]:
    global _channels_cache, _channels_loaded
    try:
        with open(channels_index, "r") as f:
            _channels_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _channels_cache = copy.deepcopy(DEFAULT_CHANNELS)
    _channels_loaded = True
    return _channels_cache


def _save_channels_index(channels: List[dict]) -> None:
    global _channels_cache, _channels_loaded
    atomic_write_json(channels_index, channels)
    _channels_cache = channels
    _channels_loaded = True
    _invalidate_permission_cache()


def _get_channels_cache() -> List[dict]:
    if not _channels_loaded:
        _load_channels_index()
    return _channels_cache


_msg_cache: Dict[str, dict] = {}


def _load_channel_into_cache(channel_name):
    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    messages = []
    offsets = []
    lengths = []

    try:
        with open(channel_file, "rb") as f:
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
    if stripped.startswith(b"["):
        try:
            messages = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            messages = []
        entry = {
            "messages": messages,
            "id_to_idx": build_id_index(messages),
            "offsets": None,
            "lengths": None,
        }
        _msg_cache[channel_name] = entry
        _full_rewrite(channel_name)
        return _msg_cache[channel_name]

    pos = 0
    for line_bytes in raw.split(b"\n"):
        content_bytes = line_bytes.rstrip(b"\r")
        line_str = content_bytes.decode("utf-8").strip()
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
        "id_to_idx": build_id_index(messages),
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

    lines = [
        json.dumps(msg, separators=(",", ":"), ensure_ascii=False) for msg in messages
    ]
    encoded_lines = [line.encode("utf-8") for line in lines]
    content_bytes = b"\n".join(encoded_lines)

    with open(tmp, "wb") as f:
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
        with open(channel_file, "rb") as f:
            raw = f.read()
    except OSError:
        return

    pos = 0
    for line_bytes in raw.split(b"\n"):
        content_bytes = line_bytes.rstrip(b"\r")
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

    new_bytes = new_serialised.encode("utf-8")
    orig_len = lengths[idx]

    if len(new_bytes) > orig_len:
        return False

    padding = orig_len - len(new_bytes)
    if padding > 0:
        new_bytes = new_bytes + b" " * padding

    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    try:
        with open(channel_file, "r+b") as f:
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
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        old_messages = cache["messages"]
        old_id_to_idx = cache["id_to_idx"]
        cache["messages"] = messages
        cache["id_to_idx"] = build_id_index(messages)
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
        with open(tmp, "w") as f:
            json.dump(DEFAULT_CHANNELS, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, channels_index)

    channels = _get_channels_cache()

    for channel in channels:
        if channel.get("type") not in ["text", "voice", "forum"]:
            continue
        channel_name = channel.get("name")
        if not channel_name:
            continue
        channel_file = os.path.join(channels_db_dir, channel_name + ".json")
        if not os.path.exists(channel_file):
            tmp = channel_file + ".tmp"
            with open(tmp, "wb") as f:
                pass
            os.replace(tmp, channel_file)


_ensure_storage()


def get_channel(channel_name):
    with _global_lock:
        for channel in _get_channels_cache():
            if channel.get("name") == channel_name:
                return copy.deepcopy(channel)
        return None


def get_channel_messages(channel_name, start, limit):
    with _get_channel_lock(channel_name):
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


def get_channel_messages_around(
    channel_name: str, message_id: str, above: int = 50, below: int = 50
) -> Tuple[Optional[List[dict]], Optional[int], Optional[int]]:
    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    return get_messages_around_from_file(channel_file, message_id, above, below)


def save_channel_message(channel_name, message, sync: bool = True):
    """Save a message to a channel.

    Args:
        channel_name: Name of the channel
        message: Message dict to save
        sync: If True, fsync to disk (slower but safer). If False, rely on OS buffering (faster).
    """
    channel_file = os.path.join(channels_db_dir, channel_name + ".json")
    os.makedirs(channels_db_dir, exist_ok=True)

    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]

        serialised = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        serialised_bytes = serialised.encode("utf-8")
        padded_bytes = serialised_bytes + b" " * MESSAGE_PADDING_SIZE

        try:
            with open(channel_file, "rb") as f:
                first_byte = f.read(1)
        except FileNotFoundError:
            first_byte = None

        if first_byte == b"[":
            messages.append(message)
            cache["id_to_idx"][message["id"]] = len(messages) - 1
            try:
                _full_rewrite(channel_name)
            except Exception:
                messages.pop()
                cache["id_to_idx"].pop(message["id"], None)
                raise
        elif first_byte is not None:
            new_offset = None
            if cache["offsets"] is not None:
                if messages:
                    new_offset = cache["offsets"][-1] + cache["lengths"][-1] + 1
                else:
                    new_offset = 0

            prefix = b"\n" if messages else b""
            with open(channel_file, "ab") as f:
                f.write(prefix + padded_bytes)
                if sync:
                    f.flush()
                    os.fsync(f.fileno())

            idx = len(messages)
            messages.append(message)
            cache["id_to_idx"][message["id"]] = idx
            if cache["offsets"] is not None and new_offset is not None:
                cache["offsets"].append(new_offset)
                cache["lengths"].append(len(padded_bytes))
            elif cache["offsets"] is None:
                _rebuild_offsets(channel_name)
        else:
            tmp = channel_file + ".tmp"
            with open(tmp, "wb") as f:
                f.write(padded_bytes)
                if sync:
                    f.flush()
                    os.fsync(f.fileno())
            os.replace(tmp, channel_file)

            messages.append(message)
            cache["id_to_idx"][message["id"]] = 0
            if cache["offsets"] is not None:
                cache["offsets"] = [0]
                cache["lengths"] = [len(padded_bytes)]

        return True


def get_all_channels():
    with _global_lock:
        return copy.deepcopy(_get_channels_cache())


def get_all_channels_for_roles(roles):
    with _global_lock:
        result = []
        for channel in _get_channels_cache():
            permissions = channel.get("permissions", {})
            view_roles = permissions.get("view", [])
            if not any(role in view_roles for role in roles):
                continue
            channel_copy = copy.deepcopy(channel)
            result.append(channel_copy)
        return result


def does_user_have_permission(channel_name, user_roles, permission_type):
    permissions = _get_channel_permissions_cached(channel_name)
    if not permissions:
        permissions = DEFAULT_PERMISSIONS

    allowed_roles = permissions.get(permission_type, [])
    return any(role in allowed_roles for role in user_roles)


def create_channel(
    channel_name,
    channel_type="text",
    description=None,
    permissions=None,
    display_name=None,
    size=None,
):
    with _global_lock:
        channels = _get_channels_cache()
        for ch in channels:
            if ch.get("name") == channel_name:
                return False

        new_channel = {
            "name": channel_name,
            "type": channel_type,
            "permissions": _normalize_permissions(permissions)
            if permissions
            else DEFAULT_PERMISSIONS,
        }
        if description:
            new_channel["description"] = description
        if display_name:
            new_channel["display_name"] = display_name
        if size is not None:
            new_channel["size"] = size

        channels.append(new_channel)
        _save_channels_index(channels)

        channel_file = os.path.join(channels_db_dir, channel_name + ".json")
        if not os.path.exists(channel_file):
            tmp = channel_file + ".tmp"
            with open(tmp, "wb") as f:
                pass
            os.replace(tmp, channel_file)

        return True


def update_channel(channel_name, updates):
    with _global_lock:
        channels = _get_channels_cache()
        for i, ch in enumerate(channels):
            if ch.get("name") == channel_name:
                if "permissions" in updates:
                    updates = {
                        **updates,
                        "permissions": _normalize_permissions(updates["permissions"]),
                    }
                channels[i] = {**ch, **updates}
                _save_channels_index(channels)
                return True
        return False


def delete_channel(channel_name):
    with _global_lock:
        channels = _get_channels_cache()
        original_len = len(channels)
        channels = [ch for ch in channels if ch.get("name") != channel_name]
        if len(channels) == original_len:
            return False

        _save_channels_index(channels)

        channel_file = os.path.join(channels_db_dir, channel_name + ".json")
        if os.path.exists(channel_file):
            os.remove(channel_file)

        if channel_name in _msg_cache:
            del _msg_cache[channel_name]

        return True


def edit_channel_message(channel_name, message_id, new_content, embeds=None):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        idx = cache["id_to_idx"].get(message_id)

        if idx is None:
            return False

        messages[idx] = messages[idx].copy()
        messages[idx]["content"] = new_content
        messages[idx]["edited"] = True
        if embeds is not None:
            messages[idx]["embeds"] = embeds

        serialised = json.dumps(
            messages[idx], separators=(",", ":"), ensure_ascii=False
        )

        if not _patch_line_in_place(channel_name, idx, serialised):
            _full_rewrite(channel_name)

        return True


def delete_channel_message(channel_name, message_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        idx = cache["id_to_idx"].get(message_id)

        if idx is None:
            return False

        messages.pop(idx)
        cache["id_to_idx"] = build_id_index(messages)
        _full_rewrite(channel_name)

        return True


def get_message_by_id(channel_name, message_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return None
        return cache["messages"][idx].copy()


def add_reaction_to_message(channel_name, message_id, emoji, user_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        idx = cache["id_to_idx"].get(message_id)

        if idx is None:
            return False

        msg = messages[idx] = messages[idx].copy()
        if "reactions" not in msg:
            msg["reactions"] = {}

        if emoji not in msg["reactions"]:
            msg["reactions"][emoji] = []

        if user_id in msg["reactions"][emoji]:
            return False

        msg["reactions"][emoji].append(user_id)

        serialised = json.dumps(msg, separators=(",", ":"), ensure_ascii=False)
        if not _patch_line_in_place(channel_name, idx, serialised):
            _full_rewrite(channel_name)

        return True


def remove_reaction_from_message(channel_name, message_id, emoji, user_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        idx = cache["id_to_idx"].get(message_id)

        if idx is None:
            return False

        msg = messages[idx] = messages[idx].copy()
        if "reactions" not in msg or emoji not in msg["reactions"]:
            return False

        if user_id in msg["reactions"][emoji]:
            msg["reactions"][emoji].remove(user_id)
            if not msg["reactions"][emoji]:
                del msg["reactions"][emoji]
            if not msg["reactions"]:
                del msg["reactions"]

            serialised = json.dumps(msg, separators=(",", ":"), ensure_ascii=False)
            if not _patch_line_in_place(channel_name, idx, serialised):
                _full_rewrite(channel_name)

            return True

        return False


def pin_channel_message(channel_name, message_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        idx = cache["id_to_idx"].get(message_id)

        if idx is None:
            return False

        messages[idx] = messages[idx].copy()
        messages[idx]["pinned"] = True

        serialised = json.dumps(
            messages[idx], separators=(",", ":"), ensure_ascii=False
        )
        if not _patch_line_in_place(channel_name, idx, serialised):
            _full_rewrite(channel_name)

        return True


def unpin_channel_message(channel_name, message_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        idx = cache["id_to_idx"].get(message_id)

        if idx is None:
            return False

        messages[idx] = messages[idx].copy()
        messages[idx]["pinned"] = False

        serialised = json.dumps(
            messages[idx], separators=(",", ":"), ensure_ascii=False
        )
        if not _patch_line_in_place(channel_name, idx, serialised):
            _full_rewrite(channel_name)

        return True


def get_pinned_messages(channel_name):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        return [msg.copy() for msg in cache["messages"] if msg.get("pinned")]


def reload_channels():
    global _channels_loaded, _msg_cache
    _channels_loaded = False
    _msg_cache = {}
    return _get_channels_cache()


def get_channel_message_count(channel_name):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        return len(cache["messages"])


def get_channel_message(channel_name, message_id):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return None
        return cache["messages"][idx].copy()


def can_user_react(channel_name, user_roles):
    channel = get_channel(channel_name)
    if not channel:
        return False
    permissions = channel.get("permissions", DEFAULT_PERMISSIONS)
    react_permission = permissions.get("react", DEFAULT_PERMISSIONS["react"])
    for role in user_roles or []:
        if role in react_permission:
            return True
    return False


def can_user_edit_own(channel_name, user_roles):
    channel = get_channel(channel_name)
    if not channel:
        return False
    permissions = channel.get("permissions", DEFAULT_PERMISSIONS)
    edit_own_permission = permissions.get("edit_own", DEFAULT_PERMISSIONS["edit_own"])
    for role in user_roles or []:
        if role in edit_own_permission:
            return True
    return False


def channel_exists(channel_name):
    with _global_lock:
        for ch in _get_channels_cache():
            if ch.get("name") == channel_name:
                return True
        return False


def get_channels():
    return get_all_channels()


def reorder_channel(channel_name, new_position):
    with _global_lock:
        channels_list = _get_channels_cache()
        channel_names = [ch.get("name") for ch in channels_list]

        if channel_name not in channel_names:
            return False

        current_idx = channel_names.index(channel_name)
        channel = channels_list.pop(current_idx)

        new_position = max(0, min(new_position, len(channels_list)))
        channels_list.insert(new_position, channel)

        _save_channels_index(channels_list)
        return True


def can_user_delete_own(channel_name, user_roles):
    channel = get_channel(channel_name)
    if not channel:
        return False
    permissions = channel.get("permissions", DEFAULT_PERMISSIONS)
    delete_own_permission = permissions.get(
        "delete_own", DEFAULT_PERMISSIONS["delete_own"]
    )
    for role in user_roles or []:
        if role in delete_own_permission:
            return True
    return False


def can_user_pin(channel_name, user_roles):
    channel = get_channel(channel_name)
    if not channel:
        return False
    permissions = channel.get("permissions", DEFAULT_PERMISSIONS)
    pin_permission = permissions.get("pin", DEFAULT_PERMISSIONS["pin"])
    for role in user_roles or []:
        if role in pin_permission:
            return True
    return False


def search_channel_messages(channel_name, query, limit=50):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        results = []
        query_lower = query.lower()
        for msg in messages:
            content = msg.get("content", "")
            if query_lower in content.lower():
                results.append(msg.copy())
                if len(results) >= limit:
                    break
        return results


def get_message_replies(channel_name, message_id, limit=50):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        replies = []
        for msg in messages:
            if msg.get("reply_to", {}).get("id") == message_id:
                replies.append(msg.copy())
                if len(replies) >= limit:
                    break
        return replies


def add_reaction(channel_name, message_id, emoji, user_id):
    return add_reaction_to_message(channel_name, message_id, emoji, user_id)


def remove_reaction(channel_name, message_id, emoji, user_id):
    return remove_reaction_from_message(channel_name, message_id, emoji, user_id)


def set_channel_permissions(channel_name, permissions):
    with _global_lock:
        channels_list = _get_channels_cache()
        for channel in channels_list:
            if channel.get("name") == channel_name:
                channel["permissions"] = permissions
                _save_channels_index(channels_list)
                return True
        return False


def purge_messages(channel_name, count=None):
    with _get_channel_lock(channel_name):
        cache = _get_channel_cache(channel_name)
        messages = cache["messages"]
        if count is None:
            messages.clear()
        else:
            del messages[:count]
        cache["id_to_idx"] = build_id_index(messages)
        _full_rewrite(channel_name)
        return True
