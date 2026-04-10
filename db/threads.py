import copy
import json
import os
import platform
import subprocess
import threading
import time
import uuid
from typing import Dict, List, Optional, Tuple

from . import users
from .shared import convert_messages_to_user_format
from .storage_utils import (
    find_line_number_grep,
    count_lines_wc,
    read_lines_range,
    get_messages_around_from_file,
    build_id_index,
)

_IS_WINDOWS = platform.system() == "Windows"
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
threads_db_dir = os.path.join(_MODULE_DIR, "threads")
thread_messages_dir = os.path.join(_MODULE_DIR, "threadMessages")

MESSAGE_PADDING_SIZE = 512

_lock = threading.RLock()
_thread_locks: Dict[str, threading.RLock] = {}
_threads_cache: Dict[str, dict] = {}
_messages_cache: Dict[str, dict] = {}


def _get_thread_lock(thread_id: str) -> threading.RLock:
    if thread_id not in _thread_locks:
        with _lock:
            if thread_id not in _thread_locks:
                _thread_locks[thread_id] = threading.RLock()
    return _thread_locks[thread_id]


def _ensure_storage():
    os.makedirs(threads_db_dir, exist_ok=True)
    os.makedirs(thread_messages_dir, exist_ok=True)


_ensure_storage()


def _get_timestamp() -> float:
    return time.time()


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
        json.dump(metadata, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, thread_file)


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
        "id_to_idx": build_id_index(messages),
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


def _patch_line_in_place(thread_id: str, idx: int, new_serialised: str) -> bool:
    cache = _messages_cache.get(thread_id)
    if cache is None or cache.get("offsets") is None:
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

    messages_file = _get_messages_file_path(thread_id)
    try:
        with open(messages_file, "r+b") as f:
            f.seek(offsets[idx])
            f.write(new_bytes)
            f.flush()
            os.fsync(f.fileno())
        return True
    except OSError:
        return False


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

    _save_thread_metadata(thread_id, metadata)
    _threads_cache[thread_id] = metadata

    _messages_cache[thread_id] = {
        "messages": [],
        "id_to_idx": {},
        "offsets": [],
        "lengths": [],
    }

    return copy.deepcopy(metadata)


def get_thread(thread_id: str) -> Optional[dict]:
    if thread_id in _threads_cache:
        return copy.deepcopy(_threads_cache[thread_id])

    metadata = _load_thread_metadata(thread_id)
    if not metadata:
        return None

    _threads_cache[thread_id] = metadata
    return metadata


def get_channel_threads(channel_name: str) -> List[dict]:
    result = []
    for filename in os.listdir(threads_db_dir):
        if filename.endswith('.json'):
            thread_id = filename[:-5]
            metadata = get_thread(thread_id)
            if metadata and metadata.get("parent_channel") == channel_name:
                result.append(metadata)
    return result


def get_thread_messages(thread_id: str, start=0, limit=100) -> List[dict]:
    cache = _get_thread_messages_cache(thread_id)
    messages = cache["messages"]

    if not messages:
        return []

    if not limit:
        limit = 100
    if limit > 200:
        limit = 200

    if isinstance(start, int):
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

    begin = max(begin, 0)
    end = min(end, len(messages))

    return list(messages[begin:end])


def save_thread_message(thread_id: str, message: dict, sync: bool = True) -> bool:
    """Save a message to a thread.

    Args:
        thread_id: ID of the thread
        message: Message dict to save
        sync: If True, fsync to disk (slower but safer). If False, rely on OS buffering (faster).
    """
    messages_file = _get_messages_file_path(thread_id)
    cache = _get_thread_messages_cache(thread_id)
    messages = cache["messages"]

    serialised = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
    serialised_bytes = serialised.encode("utf-8")
    padded_bytes = serialised_bytes + b" " * MESSAGE_PADDING_SIZE

    try:
        with open(messages_file, "rb") as f:
            first_byte = f.read(1)
    except FileNotFoundError:
        first_byte = None

    if first_byte is not None:
        new_offset = cache["offsets"][-1] + cache["lengths"][-1] + 1 if messages else 0
        prefix = b"\n" if messages else b""

        with open(messages_file, "ab") as f:
            f.write(prefix + padded_bytes)
            if sync:
                f.flush()
                os.fsync(f.fileno())

        idx = len(messages)
        messages.append(message)
        cache["id_to_idx"][message["id"]] = idx
        cache["offsets"].append(new_offset)
        cache["lengths"].append(len(padded_bytes))
    else:
        with open(messages_file, "wb") as f:
            f.write(padded_bytes)
            if sync:
                f.flush()
                os.fsync(f.fileno())

        messages.append(message)
        cache["id_to_idx"][message["id"]] = 0
        cache["offsets"] = [0]
        cache["lengths"] = [len(padded_bytes)]

    return True


def edit_thread_message(thread_id: str, message_id: str, new_content: str, embeds=None) -> bool:
    cache = _get_thread_messages_cache(thread_id)
    messages = cache["messages"]
    idx = cache["id_to_idx"].get(message_id)

    if idx is None:
        return False

    messages[idx] = messages[idx].copy()
    messages[idx]["content"] = new_content
    messages[idx]["edited"] = True
    if embeds is not None:
        messages[idx]["embeds"] = embeds

    _full_rewrite_messages(thread_id)
    return True


def delete_thread_message(thread_id: str, message_id: str) -> bool:
    cache = _get_thread_messages_cache(thread_id)
    messages = cache["messages"]
    idx = cache["id_to_idx"].get(message_id)

    if idx is None:
        return False

    messages.pop(idx)
    cache["id_to_idx"] = build_id_index(messages)
    _full_rewrite_messages(thread_id)
    return True


def get_thread_message_by_id(thread_id: str, message_id: str) -> Optional[dict]:
    cache = _get_thread_messages_cache(thread_id)
    idx = cache["id_to_idx"].get(message_id)
    if idx is None:
        return None
    return cache["messages"][idx].copy()


def add_reaction_to_thread_message(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
    with _get_thread_lock(thread_id):
        cache = _get_thread_messages_cache(thread_id)
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
        if not _patch_line_in_place(thread_id, idx, serialised):
            _full_rewrite_messages(thread_id)
        return True


def remove_reaction_from_thread_message(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
    with _get_thread_lock(thread_id):
        cache = _get_thread_messages_cache(thread_id)
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
            if not _patch_line_in_place(thread_id, idx, serialised):
                _full_rewrite_messages(thread_id)
            return True

        return False


def archive_thread(thread_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        metadata["archived"] = True
        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata
        return True


def unarchive_thread(thread_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        metadata["archived"] = False
        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata
        return True


def lock_thread(thread_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        metadata["locked"] = True
        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata
        return True


def unlock_thread(thread_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        metadata["locked"] = False
        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata
        return True


def delete_thread(thread_id: str) -> bool:
    with _lock:
        thread_file = _get_thread_file_path(thread_id)
        messages_file = _get_messages_file_path(thread_id)

        if os.path.exists(thread_file):
            os.remove(thread_file)

        if os.path.exists(messages_file):
            os.remove(messages_file)

        if thread_id in _threads_cache:
            del _threads_cache[thread_id]

        if thread_id in _messages_cache:
            del _messages_cache[thread_id]

        return True


def get_thread_participants(thread_id: str) -> List[str]:
    metadata = get_thread(thread_id)
    if not metadata:
        return []
    return metadata.get("participants", [])


def add_thread_participant(thread_id: str, user_id: str) -> bool:
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


def remove_thread_participant(thread_id: str, user_id: str) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False

        participants = metadata.get("participants", [])
        if user_id in participants and user_id != metadata.get("created_by"):
            participants.remove(user_id)
            metadata["participants"] = participants
            _save_thread_metadata(thread_id, metadata)
            _threads_cache[thread_id] = metadata
            return True

        return False


def reload_threads():
    global _threads_cache, _messages_cache
    _threads_cache = {}
    _messages_cache = {}


def is_thread_locked(thread_id: str) -> bool:
    metadata = get_thread(thread_id)
    if not metadata:
        return False
    return metadata.get("locked", False)


def is_thread_archived(thread_id: str) -> bool:
    metadata = get_thread(thread_id)
    if not metadata:
        return False
    return metadata.get("archived", False)


def update_thread(thread_id: str, updates: dict) -> bool:
    with _lock:
        metadata = get_thread(thread_id)
        if not metadata:
            return False
        for key, value in updates.items():
            metadata[key] = value
        _save_thread_metadata(thread_id, metadata)
        _threads_cache[thread_id] = metadata
        return True


def get_thread_message(thread_id: str, message_id: str) -> Optional[dict]:
    cache = _get_thread_messages_cache(thread_id)
    idx = cache["id_to_idx"].get(message_id)
    if idx is None:
        return None
    return cache["messages"][idx].copy()


def join_thread(thread_id: str, user_id: str) -> bool:
    return add_thread_participant(thread_id, user_id)


def leave_thread(thread_id: str, user_id: str) -> bool:
    return remove_thread_participant(thread_id, user_id)


def get_thread_messages_around(thread_id: str, message_id: str, above: int = 50, below: int = 50) -> Tuple[Optional[List[dict]], Optional[int], Optional[int]]:
    messages_file = _get_messages_file_path(thread_id)
    return get_messages_around_from_file(messages_file, message_id, above, below)


def add_thread_reaction(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
    return add_reaction_to_thread_message(thread_id, message_id, emoji, user_id)


def remove_thread_reaction(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
    return remove_reaction_from_thread_message(thread_id, message_id, emoji, user_id)
