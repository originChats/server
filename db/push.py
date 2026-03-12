"""
Push subscription store — flat-file JSON, keyed by username.

Schema of push_subscriptions.json:
{
    "<username>": [
        {
            "endpoint": "https://...",
            "p256dh":   "<base64url>",
            "auth":     "<base64url>"
        },
        ...
    ],
    ...
}
"""
import json, os
from typing import Optional

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_SUBS_FILE  = os.path.join(_MODULE_DIR, "push_subscriptions.json")


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(_SUBS_FILE):
        with open(_SUBS_FILE, "w") as f:
            json.dump({}, f, indent=4)


_ensure_storage()


def _load() -> dict:
    try:
        with open(_SUBS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict):
    # Write to a temp file then rename for atomic replacement
    tmp = _SUBS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, _SUBS_FILE)


def upsert_subscription(username: str, endpoint: str, p256dh: str, auth: str):
    """
    Insert or replace a push subscription for a given endpoint.
    If the endpoint already exists for this user it is updated in-place;
    otherwise a new entry is appended.
    """
    username = username.lower()
    data = _load()
    subs = data.get(username, [])

    # Replace existing entry for this endpoint, or append a new one
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
    data = _load()

    if username is not None:
        # Fast path: only touch the named user's list
        subs = data.get(username, [])
        new_subs = [s for s in subs if s.get("endpoint") != endpoint]
        if len(new_subs) != len(subs):
            data[username] = new_subs
            _save(data)
    else:
        # Scan all users (used by stale-subscription cleanup in push handler)
        changed = False
        for uname, subs in data.items():
            new_subs = [s for s in subs if s.get("endpoint") != endpoint]
            if len(new_subs) != len(subs):
                data[uname] = new_subs
                changed = True
        if changed:
            _save(data)


def get_subscriptions_for_user(username: str) -> list:
    """
    Return all subscription records for *username* as a list of dicts,
    each containing keys: endpoint, p256dh, auth.
    """
    data = _load()
    return list(data.get(username.lower(), []))
