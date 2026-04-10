import json
import os
import threading
from typing import Dict, Optional, Tuple

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_UNREADS_FILE = os.path.join(_MODULE_DIR, "unreads.json")

_lock = threading.RLock()
_cache: Dict[str, Dict[str, str]] = {}
_loaded: bool = False


def _load() -> Dict[str, Dict[str, str]]:
    global _cache, _loaded
    try:
        with open(_UNREADS_FILE, "r") as f:
            _cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cache = {}
    _loaded = True
    return _cache


def _save(data: Dict[str, Dict[str, str]]) -> None:
    global _cache, _loaded
    tmp = _UNREADS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _UNREADS_FILE)
    _cache = data
    _loaded = True


def _get_cache() -> Dict[str, Dict[str, str]]:
    if not _loaded:
        _load()
    return _cache


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(_UNREADS_FILE):
        tmp = _UNREADS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({}, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _UNREADS_FILE)


_ensure_storage()


def get_last_read(user_id: str, channel: Optional[str] = None, thread_id: Optional[str] = None) -> Optional[str]:
    key = f"thread/{thread_id}" if thread_id else channel
    if not key:
        return None
    with _lock:
        user_unreads = _get_cache().get(user_id, {})
        return user_unreads.get(key)


def set_last_read(user_id: str, message_id: str, channel: Optional[str] = None, thread_id: Optional[str] = None) -> bool:
    key = f"thread/{thread_id}" if thread_id else channel
    if not key or not message_id:
        return False
    with _lock:
        data = _get_cache()
        if user_id not in data:
            data[user_id] = {}
        data[user_id][key] = message_id
        _save(data)
    return True


def get_all_last_reads(user_id: str) -> Dict[str, str]:
    with _lock:
        return dict(_get_cache().get(user_id, {}))


def get_unread_count_for_channel(user_id: str, channel: str, messages: list) -> Tuple[int, Optional[str]]:
    last_read = get_last_read(user_id, channel=channel)
    if not last_read:
        return len(messages), None

    for i, msg in enumerate(messages):
        if msg.get("id") == last_read:
            return len(messages) - i - 1, last_read
    return len(messages), last_read


def get_unread_count_for_thread(user_id: str, thread_id: str, messages: list) -> Tuple[int, Optional[str]]:
    last_read = get_last_read(user_id, thread_id=thread_id)
    if not last_read:
        return len(messages), None

    for i, msg in enumerate(messages):
        if msg.get("id") == last_read:
            return len(messages) - i - 1, last_read
    return len(messages), last_read


def delete_user_unreads(user_id: str) -> bool:
    with _lock:
        data = _get_cache()
        if user_id in data:
            del data[user_id]
            _save(data)
            return True
        return False


def delete_channel_unreads(channel: str) -> bool:
    with _lock:
        data = _get_cache()
        changed = False
        for user_id in list(data.keys()):
            if channel in data[user_id]:
                del data[user_id][channel]
                changed = True
        if changed:
            _save(data)
        return changed


def delete_thread_unreads(thread_id: str) -> bool:
    key = f"thread/{thread_id}"
    with _lock:
        data = _get_cache()
        changed = False
        for user_id in list(data.keys()):
            if key in data[user_id]:
                del data[user_id][key]
                changed = True
        if changed:
            _save(data)
        return changed
