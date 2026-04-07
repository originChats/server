import copy
import json
import os
import threading
import time
import uuid
from typing import Dict, List, Optional

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
webhooks_file = os.path.join(_MODULE_DIR, "webhooks.json")

DEFAULT_WEBHOOKS: Dict[str, dict] = {}

_lock = threading.RLock()
_webhooks_cache: Dict[str, dict] = {}
_webhooks_loaded: bool = False


def _load_webhooks() -> Dict[str, dict]:
    global _webhooks_cache, _webhooks_loaded
    try:
        with open(webhooks_file, "r") as f:
            _webhooks_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _webhooks_cache = {}
    _webhooks_loaded = True
    return _webhooks_cache


def _save_webhooks(webhooks_dict: Dict[str, dict]) -> None:
    global _webhooks_cache, _webhooks_loaded
    tmp = webhooks_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(webhooks_dict, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, webhooks_file)
    _webhooks_cache = webhooks_dict
    _webhooks_loaded = True


def _get_webhooks_cache() -> Dict[str, dict]:
    if not _webhooks_loaded:
        _load_webhooks()
    return _webhooks_cache


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(webhooks_file):
        tmp = webhooks_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(DEFAULT_WEBHOOKS, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, webhooks_file)


_ensure_storage()


def create_webhook(channel: str, name: str, created_by: str, avatar: Optional[str] = None) -> dict:
    webhook_id = str(uuid.uuid4())
    token = str(uuid.uuid4()) + str(uuid.uuid4()).replace("-", "")

    webhook_data = {
        "id": webhook_id,
        "channel": channel,
        "name": name,
        "token": token,
        "created_by": created_by,
        "created_at": time.time(),
        "avatar": avatar
    }

    with _lock:
        webhooks = _get_webhooks_cache()
        webhooks[webhook_id] = webhook_data
        _save_webhooks(webhooks)

    return webhook_data


def get_webhook(webhook_id: str) -> Optional[dict]:
    with _lock:
        webhook = _get_webhooks_cache().get(webhook_id)
        return copy.deepcopy(webhook) if webhook else None


def get_webhook_by_token(token: str) -> Optional[dict]:
    with _lock:
        for webhook in _get_webhooks_cache().values():
            if webhook.get("token") == token:
                return copy.deepcopy(webhook)
    return None


def get_webhooks_for_channel(channel: str) -> List[dict]:
    with _lock:
        result = []
        for webhook in _get_webhooks_cache().values():
            if webhook.get("channel") == channel:
                result.append(copy.deepcopy(webhook))
        return result


def get_all_webhooks() -> List[dict]:
    with _lock:
        return [copy.deepcopy(w) for w in _get_webhooks_cache().values()]


def delete_webhook(webhook_id: str) -> bool:
    with _lock:
        webhooks = _get_webhooks_cache()
        if webhook_id in webhooks:
            del webhooks[webhook_id]
            _save_webhooks(webhooks)
            return True
        return False


def update_webhook(webhook_id: str, updates: dict) -> Optional[dict]:
    with _lock:
        webhooks = _get_webhooks_cache()
        if webhook_id not in webhooks:
            return None

        if "name" in updates:
            webhooks[webhook_id]["name"] = updates["name"]
        if "avatar" in updates:
            webhooks[webhook_id]["avatar"] = updates["avatar"]

        _save_webhooks(webhooks)
        return copy.deepcopy(webhooks[webhook_id])


def webhook_exists_for_channel(channel: str, webhook_id: str) -> bool:
    with _lock:
        webhook = _get_webhooks_cache().get(webhook_id)
        return webhook is not None and webhook.get("channel") == channel


def get_webhook_owner(webhook_id: str) -> Optional[str]:
    with _lock:
        webhook = _get_webhooks_cache().get(webhook_id)
        return webhook.get("created_by") if webhook else None
