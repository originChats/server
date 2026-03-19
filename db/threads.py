import copy
import json
import os
import threading
import uuid
from typing import Dict, List, Optional
from . import users
from .emoji_utils import is_valid_emoji

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
threads_db_dir = os.path.join(_MODULE_DIR, "threads")
thread_messages_dir = os.path.join(_MODULE_DIR, "threadMessages")

_lock = threading.RLock()

_threads_cache: Dict[str, dict] = {}
_messages_cache: Dict[str, dict] = {}


def _ensure_storage():
	os.makedirs(threads_db_dir, exist_ok=True)
	os.makedirs(thread_messages_dir, exist_ok=True)


_ensure_storage()


def _get_thread_file_path(thread_id: str) -> str:
    return os.path.join(threads_db_dir, f"{thread_id}.json")


def _get_messages_file_path(thread_id: str) -> str:
	return os.path.join(thread_messages_dir, f"{thread_id}.jsonl")


def _load_thread_metadata(thread_id: str) -> Optional[dict]:
    thread_file = _get_thread_file_path(thread_id)
    try:
        with open(thread_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_thread_metadata(thread_id: str, metadata: dict) -> None:
    thread_file = _get_thread_file_path(thread_id)
    tmp = thread_file + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(metadata, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, thread_file)


def _build_id_index(messages):
    return {msg["id"]: i for i, msg in enumerate(messages) if "id" in msg}


def _load_thread_messages(thread_id: str) -> dict:
    messages_file = _get_messages_file_path(thread_id)
    messages = []
    offsets = []
    lengths = []

    try:
        with open(messages_file, 'rb') as f:
            raw = f.read()
    except FileNotFoundError:
        return {
            "messages": [],
            "id_to_idx": {},
            "offsets": [],
            "lengths": [],
        }

    if not raw.strip():
        return {
            "messages": [],
            "id_to_idx": {},
            "offsets": [],
            "lengths": [],
        }

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

    return {
        "messages": messages,
        "id_to_idx": _build_id_index(messages),
        "offsets": offsets,
        "lengths": lengths,
    }


def _get_thread_messages_cache(thread_id: str) -> dict:
    if thread_id not in _messages_cache:
        _messages_cache[thread_id] = _load_thread_messages(thread_id)
    return _messages_cache[thread_id]


def _full_rewrite_messages(thread_id: str):
    cache = _messages_cache.get(thread_id)
    if cache is None:
        return

    messages = cache["messages"]
    messages_file = _get_messages_file_path(thread_id)
    tmp = messages_file + ".tmp"

    lines = [json.dumps(msg, separators=(',', ':'), ensure_ascii=False) for msg in messages]
    encoded_lines = [line.encode('utf-8') for line in lines]
    content_bytes = b'\n'.join(encoded_lines)

    with open(tmp, 'wb') as f:
        f.write(content_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, messages_file)

    offsets = []
    lengths = []
    pos = 0
    for lb in encoded_lines:
        offsets.append(pos)
        lengths.append(len(lb))
        pos += len(lb) + 1

    cache["offsets"] = offsets
    cache["lengths"] = lengths


def create_thread(parent_channel: str, name: str, creator: str) -> dict:
    thread_id = str(uuid.uuid4())

    metadata = {
        "id": thread_id,
        "name": name,
        "parent_channel": parent_channel,
        "created_by": creator,
        "created_at": _get_timestamp(),
        "locked": False,
        "archived": False,
        "participants": [creator],
    }

    with _lock:
        _ensure_storage()
        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata
        _messages_cache[thread_id] = {
            "messages": [],
            "id_to_idx": {},
            "offsets": [],
            "lengths": [],
        }

    return copy.deepcopy(metadata)


def _get_timestamp() -> float:
    import time
    return time.time()


def get_thread(thread_id: str) -> Optional[dict]:
    with _lock:
        if thread_id in _threads_cache:
            return copy.deepcopy(_threads_cache[thread_id])

        metadata = _load_thread_metadata(thread_id)
        if metadata:
            created_by = metadata.get("created_by")
            participants = metadata.get("participants", [])
            if created_by and created_by not in participants:
                participants.append(created_by)
                metadata["participants"] = participants
                _save_thread_metadata(thread_id, metadata)
            _threads_cache[thread_id] = metadata
            return metadata


def get_channel_threads(channel_name: str) -> List[dict]:
    threads = []
    with _lock:
        for filename in os.listdir(threads_db_dir):
            if filename.endswith('.json') and not filename.endswith('_messages.jsonl'):
                thread_id = filename[:-5]
                metadata = get_thread(thread_id)
                if metadata and metadata.get("parent_channel") == channel_name:
                    threads.append(metadata)
    
    threads.sort(key=lambda t: t.get("created_at", 0), reverse=True)
    return threads


def delete_thread(thread_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        thread_file = _get_thread_file_path(thread_id)
        messages_file = _get_messages_file_path(thread_id)

        try:
            os.remove(thread_file)
        except OSError:
            pass

        try:
            os.remove(messages_file)
        except OSError:
            pass

        _threads_cache.pop(thread_id, None)
        _messages_cache.pop(thread_id, None)

        return True


def update_thread(thread_id: str, updates: dict) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        for key in ["name", "locked", "archived", "participants"]:
            if key in updates:
                metadata[key] = updates[key]

        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata

        return True


def save_thread_message(thread_id: str, message: dict) -> bool:
    messages_file = _get_messages_file_path(thread_id)

    with _lock:
        cache = _get_thread_messages_cache(thread_id)
        messages = cache["messages"]

        serialised = json.dumps(message, separators=(',', ':'), ensure_ascii=False)
        serialised_bytes = serialised.encode('utf-8')

        new_offset: Optional[int] = None
        if cache["offsets"] is not None:
            if messages:
                new_offset = cache["offsets"][-1] + cache["lengths"][-1] + 1
            else:
                new_offset = 0

        prefix = b'\n' if messages else b''
        with open(messages_file, 'ab') as f:
            f.write(prefix + serialised_bytes)
            f.flush()
            os.fsync(f.fileno())

        idx = len(messages)
        messages.append(message)
        cache["id_to_idx"][message["id"]] = idx
        if cache["offsets"] is not None and new_offset is not None:
            cache["offsets"].append(new_offset)
            cache["lengths"].append(len(serialised_bytes))

        return True


def get_thread_messages(thread_id: str, start=None, limit=100) -> List[dict]:
    with _lock:
        cache = _get_thread_messages_cache(thread_id)
        messages = cache["messages"]

        if not messages:
            return []

        if limit > 200:
            limit = 200

        if start is None:
            begin = max(0, len(messages) - limit)
            end = len(messages)
        elif isinstance(start, int):
            if start < 0:
                start = 0
            end = len(messages) - start
            begin = max(0, end - limit)
        else:
            idx = cache["id_to_idx"].get(start)
            if idx is None:
                return []
            end = idx
            begin = max(0, end - limit)

        if begin >= len(messages):
            return []

        return [copy.deepcopy(msg) for msg in messages[begin:end]]


def get_thread_message(thread_id: str, message_id: str) -> Optional[dict]:
    with _lock:
        cache = _get_thread_messages_cache(thread_id)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return None
        msg = copy.deepcopy(cache["messages"][idx])
        msg["position"] = idx + 1
        return msg


def edit_thread_message(thread_id: str, message_id: str, new_content: str, embeds=None) -> bool:
    with _lock:
        cache = _get_thread_messages_cache(thread_id)
        id_to_idx = cache["id_to_idx"]

        if message_id not in id_to_idx:
            return False

        idx = id_to_idx[message_id]
        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        msg["content"] = new_content
        msg["edited"] = True
        if embeds is not None:
            msg["embeds"] = embeds

        cache["messages"][idx] = msg
        _full_rewrite_messages(thread_id)

        return True


def delete_thread_message(thread_id: str, message_id: str) -> bool:
    with _lock:
        cache = _get_thread_messages_cache(thread_id)

        if message_id not in cache["id_to_idx"]:
            return True

        new_messages = [m for m in cache["messages"] if m.get("id") != message_id]
        cache["messages"] = new_messages
        cache["id_to_idx"] = _build_id_index(new_messages)
        _full_rewrite_messages(thread_id)

        return True


def convert_messages_to_user_format(messages: List[dict]) -> List[dict]:
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


def thread_exists(thread_id: str) -> bool:
    return get_thread(thread_id) is not None


def is_thread_locked(thread_id: str) -> bool:
    metadata = get_thread(thread_id)
    if not metadata:
        return True
    return metadata.get("locked", False)


def is_thread_archived(thread_id: str) -> bool:
    metadata = get_thread(thread_id)
    if not metadata:
        return True
    return metadata.get("archived", False)


def join_thread(thread_id: str, user_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        participants = metadata.get("participants", [])
        if user_id not in participants:
            participants.append(user_id)
            metadata["participants"] = participants
            _save_thread_metadata(thread_id, metadata)
            _threads_cache[thread_id] = metadata

        return True


def leave_thread(thread_id: str, user_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        participants = metadata.get("participants", [])
        if user_id in participants:
            participants.remove(user_id)
            metadata["participants"] = participants
            _save_thread_metadata(thread_id, metadata)
            _threads_cache[thread_id] = metadata

        return True


def get_thread_participants(thread_id: str) -> List[str]:
    metadata = get_thread(thread_id)
    if not metadata:
        return []
    return metadata.get("participants", [])


def add_thread_reaction(thread_id, message_id, emoji_str, user_id):
    """
    Add a reaction to a message in a thread.

    Args:
        thread_id (str): The ID of the thread.
        message_id (str): The ID of the message to add the reaction to.
        emoji_str (str): The emoji to add.
        user_id (str): The ID of the user to add the reaction for.

    Returns:
        bool: True if the reaction was added successfully, False otherwise.
    """
    with _lock:
        cache = _get_thread_messages_cache(thread_id)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return False

        if not is_valid_emoji(emoji_str):
            return False

        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)
        msg.setdefault("reactions", {})
        msg["reactions"].setdefault(emoji_str, [])

        if user_id in msg["reactions"][emoji_str]:
            return True

        msg["reactions"][emoji_str].append(user_id)
        cache["messages"][idx] = msg
        _full_rewrite_messages(thread_id)

    return True


def remove_thread_reaction(thread_id, message_id, emoji_str, user_id):
    """
    Remove a reaction from a message in a thread.

    Args:
        thread_id (str): The ID of the thread.
        message_id (str): The ID of the message to remove the reaction from.
        emoji_str (str): The emoji to remove.
        user_id (str): The ID of the user to remove the reaction for.

    Returns:
        bool: True if the reaction was removed successfully, False otherwise.
    """
    with _lock:
        cache = _get_thread_messages_cache(thread_id)
        idx = cache["id_to_idx"].get(message_id)
        if idx is None:
            return False

        if not is_valid_emoji(emoji_str):
            return False

        old_msg = cache["messages"][idx]
        msg = copy.deepcopy(old_msg)

        if "reactions" not in msg or emoji_str not in msg["reactions"]:
            return True

        if user_id in msg["reactions"][emoji_str]:
            msg["reactions"][emoji_str].remove(user_id)

        if not msg["reactions"][emoji_str]:
            del msg["reactions"][emoji_str]

        if not msg["reactions"]:
            del msg["reactions"]

        cache["messages"][idx] = msg
        _full_rewrite_messages(thread_id)

    return True
