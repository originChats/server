import copy
import json
import os
import threading
import time
from typing import Dict, List, Optional

from logger import Logger
from config_store import get_config_value

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_log_path = os.path.join(_MODULE_DIR, "modlog.json")

_lock = threading.RLock()
_log_cache: List[dict] = []
_loaded: bool = False


def _load() -> List[dict]:
    global _log_cache, _loaded
    try:
        with open(_log_path, "r") as f:
            _log_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _log_cache = []
    _loaded = True
    return _log_cache


def _save(entries: List[dict]) -> None:
    global _log_cache, _loaded
    tmp = _log_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _log_path)
    _log_cache = entries
    _loaded = True


def _ensure_storage() -> None:
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(_log_path):
        _save([])


_ensure_storage()


def _retention_seconds(category: str) -> int:
    from constants import FALLBACK_RETENTION_DAYS

    days = get_config_value("modlog", "retention", category)
    if days is None:
        days = get_config_value("modlog", "retention", "default")
    if days is None:
        days = FALLBACK_RETENTION_DAYS
    return int(days) * 86400


def log_action(
    action: str,
    actor_id: str,
    actor_name: str,
    *,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    details: Optional[dict] = None,
    category: Optional[str] = None,
) -> dict:
    from constants import AUDIT_CATEGORIES

    if category is None:
        category = AUDIT_CATEGORIES.get(action, "other")

    entry = {
        "id": f"{int(time.time() * 1000)}-{actor_id}",
        "action": action,
        "category": category,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_id": target_id,
        "target_name": target_name,
        "details": details or {},
        "timestamp": time.time(),
    }

    with _lock:
        entries = _get_cache()
        entries.append(entry)
        _save(entries)

    return copy.deepcopy(entry)


def get_log(
    *,
    category: Optional[str] = None,
    actor_id: Optional[str] = None,
    target_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    after: Optional[float] = None,
) -> dict:
    _expire()

    with _lock:
        entries = _get_cache()

    results = entries

    if category:
        results = [e for e in results if e.get("category") == category]
    if actor_id:
        results = [e for e in results if e.get("actor_id") == actor_id]
    if target_id:
        results = [e for e in results if e.get("target_id") == target_id]
    if action:
        results = [e for e in results if e.get("action") == action]
    if after is not None:
        results = [e for e in results if e.get("timestamp", 0) > after]

    results = sorted(results, key=lambda e: e.get("timestamp", 0), reverse=True)

    total = len(results)
    page = results[offset : offset + limit]

    return {
        "entries": copy.deepcopy(page),
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_cache() -> List[dict]:
    if not _loaded:
        _load()
    return _log_cache


def _expire() -> int:
    with _lock:
        entries = _get_cache()
        now = time.time()
        before = len(entries)

        kept = []
        for entry in entries:
            ttl = _retention_seconds(entry.get("category", "other"))
            if now - entry.get("timestamp", 0) < ttl:
                kept.append(entry)

        if len(kept) < before:
            _save(kept)
            purged = before - len(kept)
            Logger.info(f"ModLog: purged {purged} expired entries")
            return purged

    return 0


def expire_all() -> int:
    return _expire()
