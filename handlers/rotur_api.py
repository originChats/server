import time
import json
import threading
from typing import Dict, Optional, Tuple
import requests
from logger import Logger
from config_store import get_config_value
from db import users

ROTUR_PROFILE_URL = "https://api.rotur.dev/profile"

_subscription_cache: Dict[str, Tuple[str, float]] = {}
_cache_lock = threading.RLock()


def get_cache_ttl() -> int:
    return get_config_value("attachments", "subscription_cache_ttl", default=300)


def get_permanent_tiers() -> list:
    tiers = get_config_value("attachments", "permanent_tiers", default=["pro", "max"])
    return [t.lower() for t in tiers]


def _is_cracked_mode() -> bool:
    auth_mode = get_config_value("auth_mode", default="rotur")
    return auth_mode in ("cracked", "cracked-only")


def get_user_subscription(username: str) -> Optional[str]:
    user_id = users.get_id_by_username(username)
    if user_id and users.is_cracked_user(user_id):
        return "none"

    cache_key = username.lower()
    cache_ttl = get_cache_ttl()

    with _cache_lock:
        if cache_key in _subscription_cache:
            cached_tier, cached_time = _subscription_cache[cache_key]
            if time.time() - cached_time < cache_ttl:
                return cached_tier

    if _is_cracked_mode():
            _subscription_cache[cache_key] = ("none", time.time())
            return "none"

    try:
        response = requests.get(
            ROTUR_PROFILE_URL,
            params={"include_posts": 0, "name": username},
            timeout=10
        )

        if response.status_code != 200:
            Logger.warning(f"Rotur API returned {response.status_code} for user {username}")
            return None

        data = response.json()
        subscription = data.get("subscription", "none")

        if isinstance(subscription, str):
            tier = subscription.lower()
        else:
            tier = "none"

        with _cache_lock:
            _subscription_cache[cache_key] = (tier, time.time())

        Logger.info(f"Rotur subscription for {username}: {tier}")
        return tier

    except requests.RequestException as e:
        Logger.error(f"Failed to fetch Rotur profile for {username}: {e}")
        return None
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        Logger.error(f"Failed to parse Rotur profile for {username}: {e}")
        return None


def has_permanent_upload(username: str) -> bool:
    tier = get_user_subscription(username)
    if tier is None:
        return False

    permanent_tiers = get_permanent_tiers()
    return tier in permanent_tiers


def clear_subscription_cache(username: Optional[str] = None) -> None:
    with _cache_lock:
        if username:
            _subscription_cache.pop(username.lower(), None)
        else:
            _subscription_cache.clear()
