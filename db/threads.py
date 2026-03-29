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
from .emoji_utils import is_valid_emoji

_IS_WINDOWS = platform.system() == "Windows"
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

    serialised = json.dumps(message, separators=(',', ':'), ensure_ascii=False)
    serialised_bytes = serialised.encode('utf-8')

    try:
        with open(messages_file, 'rb') as f:
            first_byte = f.read(1)
    except FileNotFoundError:
        first_byte = None

    if first_byte is not None:
        new_offset = cache["offsets"][-1] + cache["lengths"][-1] + 1 if messages else 0
        prefix = b'\n' if messages else b''

        with open(messages_file, 'ab') as f:
            f.write(prefix + serialised_bytes)
            if sync:
                f.flush()
                os.fsync(f.fileno())

        idx = len(messages)
        messages.append(message)
        cache["id_to_idx"][message["id"]] = idx
        cache["offsets"].append(new_offset)
        cache["lengths"].append(len(serialised_bytes))
    else:
        with open(messages_file, 'w') as f:
            f.write(serialised)
            if sync:
                f.flush()
                os.fsync(f.fileno())

        messages.append(message)
        cache["id_to_idx"][message["id"]] = 0
        cache["offsets"] = [0]
        cache["lengths"] = [len(serialised_bytes)]

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
    cache["id_to_idx"] = _build_id_index(messages)
    _full_rewrite_messages(thread_id)
    return True


def get_thread_message_by_id(thread_id: str, message_id: str) -> Optional[dict]:
    cache = _get_thread_messages_cache(thread_id)
    idx = cache["id_to_idx"].get(message_id)
    if idx is None:
        return None
    return cache["messages"][idx].copy()


def add_reaction_to_thread_message(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
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
    _full_rewrite_messages(thread_id)
    return True


def remove_reaction_from_thread_message(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
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

        msg_copy.setdefault("pinned", False)
        msg_copy.setdefault("type", "message")

        converted.append(msg_copy)

    return converted


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
    return _get_messages_around_from_file(messages_file, message_id, above, below)


def _find_line_number_grep(file_path: str, search_pattern: str) -> Optional[int]:
    """Use grep to find line number of a pattern. Returns 0-indexed line number."""
    if _IS_WINDOWS:
        return None
    try:
        result = subprocess.run(
            ["grep", "-n", "-F", search_pattern, file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout:
            first_match = result.stdout.split("\n")[0]
            if ":" in first_match:
                return int(first_match.split(":")[0]) - 1
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def _count_lines_wc(file_path: str) -> int:
    """Use wc to count lines in a file."""
    if _IS_WINDOWS:
        return 0
    try:
        result = subprocess.run(
            ["wc", "-l", file_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return 0


def _read_lines_range(file_path: str, start: int, end: int) -> List[dict]:
    """Read a range of lines from a file using sed on Unix, or pure Python on Windows."""
    messages = []
    
    if not _IS_WINDOWS:
        try:
            result = subprocess.run(
                ["sed", "-n", f"{start+1},{end}p", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                return messages
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if idx >= start and idx < end:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            elif idx >= end:
                break
    return messages


def _get_messages_around_from_file(file_path: str, message_id: str, above: int = 50, below: int = 50) -> Tuple[Optional[List[dict]], Optional[int], Optional[int]]:
    if not os.path.exists(file_path):
        return None, None, None

    above = max(0, min(above, 200))
    below = max(0, min(below, 200))

    if not _IS_WINDOWS:
        target_idx = _find_line_number_grep(file_path, f'"id":"{message_id}"')
        if target_idx is None:
            return None, None, None
        
        total_lines = _count_lines_wc(file_path)
        if total_lines == 0:
            total_lines = target_idx + 1
        
        start_line = max(0, target_idx - below)
        end_line = min(total_lines, target_idx + above + 1)
        
        messages = _read_lines_range(file_path, start_line, end_line)
        return messages, start_line, end_line

    target_idx = None
    total_lines = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            total_lines = idx + 1
            if target_idx is None and f'"id":"{message_id}"' in line:
                target_idx = idx

    if target_idx is None:
        return None, None, None

    start_line = max(0, target_idx - below)
    end_line = min(total_lines, target_idx + above + 1)

    messages = _read_lines_range(file_path, start_line, end_line)
    return messages, start_line, end_line


def add_thread_reaction(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
    return add_reaction_to_thread_message(thread_id, message_id, emoji, user_id)


def remove_thread_reaction(thread_id: str, message_id: str, emoji: str, user_id: str) -> bool:
    return remove_reaction_from_thread_message(thread_id, message_id, emoji, user_id)
