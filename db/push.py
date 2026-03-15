import json
import os
import threading
import hashlib
import hmac
from typing import Optional

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_SUBS_FILE = os.path.join(_MODULE_DIR, "push_subscriptions.json")
_FINGERPRINT_SECRET = os.environ.get("PUSH_FINGERPRINT_SECRET", "originchats-push-secret")

_lock = threading.RLock()
_cache: dict = {}
_loaded: bool = False


def compute_device_fingerprint(ip: str, user_agent: str, country: str = "") -> str:
    """
    Generate a unique device fingerprint using HMAC.
    
    Args:
        ip: Client IP address (from CF-Connecting-IP or X-Forwarded-For)
        user_agent: Browser user agent string
        country: Country code from Cloudflare (CF-IPCountry header)
    
    Returns:
        A 16-character device fingerprint
    """
    payload = f"{ip}|{user_agent}|{country}"
    signature = hmac.new(
        _FINGERPRINT_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    return signature


def _load() -> dict:
    global _cache, _loaded
    try:
        with open(_SUBS_FILE, "r") as f:
            _cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cache = {}
    _loaded = True
    return _cache


def _save(data: dict) -> None:
    global _cache, _loaded
    tmp = _SUBS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _SUBS_FILE)
    _cache = data
    _loaded = True


def _get_cache() -> dict:
    if not _loaded:
        _load()
    return _cache


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(_SUBS_FILE):
        tmp = _SUBS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({}, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _SUBS_FILE)


_ensure_storage()


def upsert_subscription(username: str, endpoint: str, p256dh: str, auth: str, device_fingerprint: str | None = None):
    """
    Insert or replace a push subscription for a given device.
    
    If device_fingerprint is provided, only one subscription per device is stored.
    If the device already has a subscription, it is replaced.
    """
    username = username.lower()
    with _lock:
        data = dict(_get_cache())
        subs = list(data.get(username, []))
        
        if device_fingerprint:
            for i, sub in enumerate(subs):
                if sub.get("device_fingerprint") == device_fingerprint:
                    subs[i] = {
                        "endpoint": endpoint,
                        "p256dh": p256dh,
                        "auth": auth,
                        "device_fingerprint": device_fingerprint
                    }
                    break
            else:
                subs.append({
                    "endpoint": endpoint,
                    "p256dh": p256dh,
                    "auth": auth,
                    "device_fingerprint": device_fingerprint
                })
        else:
            for i, sub in enumerate(subs):
                if sub.get("endpoint") == endpoint:
                    subs[i] = {"endpoint": endpoint, "p256dh": p256dh, "auth": auth}
                    break
            else:
                subs.append({"endpoint": endpoint, "p256dh": p256dh, "auth": auth})
        
        data[username] = subs
        _save(data)


def delete_subscription(endpoint: str, username: Optional[str] = None):
    """
    Remove a subscription by endpoint.
    If *username* is provided the deletion is scoped to that user
    (prevents one user from deleting another user's subscription).
    """
    if username is not None:
        username = username.lower()
    
    with _lock:
        data = dict(_get_cache())
        
        if username is not None:
            subs = data.get(username, [])
            new_subs = [s for s in subs if s.get("endpoint") != endpoint]
            if len(new_subs) != len(subs):
                data[username] = new_subs
                _save(data)
        else:
            changed = False
            for uname, subs in data.items():
                new_subs = [s for s in subs if s.get("endpoint") != endpoint]
                if len(new_subs) != len(subs):
                    data[uname] = new_subs
                    changed = True
            if changed:
                _save(data)


def delete_subscription_by_fingerprint(username: str, device_fingerprint: str):
    """Remove a subscription by device fingerprint for a specific user."""
    username = username.lower()
    with _lock:
        data = dict(_get_cache())
        subs = data.get(username, [])
        new_subs = [s for s in subs if s.get("device_fingerprint") != device_fingerprint]
        if len(new_subs) != len(subs):
            data[username] = new_subs
            _save(data)


def get_subscriptions_for_user(username: str) -> list:
    """
    Return all subscription records for *username* as a list of dicts,
    each containing keys: endpoint, p256dh, auth.
    """
    with _lock:
        return list(_get_cache().get(username.lower(), []))
