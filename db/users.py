import copy
import json
import os
import secrets
import threading
import sys
import bcrypt
from typing import Dict, Optional

from . import roles
from constants import ALLOWED_STATUSES

from logger import Logger
from config_store import get_config_value

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
users_index = os.path.join(_MODULE_DIR, "users.json")

DEFAULT_USERS: Dict[str, dict] = {}

_lock = threading.RLock()
_users_cache: Dict[str, dict] = {}
_users_loaded: bool = False

DEFAULT_STATUS = {"status": "online", "text": ""}


def _load_users() -> Dict[str, dict]:
    global _users_cache, _users_loaded
    try:
        with open(users_index, "r") as f:
            _users_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _users_cache = {}
    _users_loaded = True
    return _users_cache


def reload_users() -> Dict[str, dict]:
    global _users_loaded
    _users_loaded = False
    return _load_users()


def _save_users(users_dict: Dict[str, dict]) -> None:
    global _users_cache, _users_loaded
    tmp = users_index + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users_dict, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, users_index)
    _users_cache = users_dict
    _users_loaded = True


def _get_users_cache() -> Dict[str, dict]:
    if not _users_loaded:
        _load_users()
    return _users_cache


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(users_index):
        tmp = users_index + ".tmp"
        with open(tmp, "w") as f:
            json.dump(DEFAULT_USERS, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, users_index)


_ensure_storage()


def user_exists(user_id):
    with _lock:
        return user_id in _get_users_cache()


def get_user(user_id):
    with _lock:
        user = _get_users_cache().get(user_id)
        return copy.deepcopy(user) if user is not None else None


def add_user(user_id, username=None, default_roles=None):
    with _lock:
        if user_exists(user_id):
            return False

        user_data = get_config_value("DB", "users", "default", default={}).copy()

        if username:
            user_data["username"] = username
        elif "username" not in user_data:
            user_data["username"] = user_id

        if default_roles:
            user_data["roles"] = default_roles
        elif "roles" not in user_data:
            user_data["roles"] = []
        if "status" not in user_data:
            user_data["status"] = DEFAULT_STATUS

        users = _get_users_cache()
        users[user_id] = user_data
        _save_users(users)
        return True


def get_user_roles(user_id):
    user = get_user(user_id)
    if user:
        return user.get("roles", [])
    return []


def get_users():
    with _lock:
        users = _get_users_cache()
        user_arr = []

        for user_id, user_data in users.items():
            if "banned" in user_data.get("roles", []):
                continue

            user_roles = user_data.get("roles", [])
            color = roles.get_user_color(user_roles)

            user_status = user_data.get("status", DEFAULT_STATUS)
            username = user_data.get("username", user_id)
            nickname = user_data.get("nickname")
            pfp_url = user_data.get("pfp_url")
            is_cracked = user_id.startswith(CRACKED_USER_PREFIX)

            user_arr.append(
                {
                    "username": username,
                    "nickname": nickname,
                    "roles": list(user_roles),
                    "color": color,
                    "status": user_status,
                    "cracked": is_cracked,
                    "pfp": pfp_url,
                }
            )

        return user_arr


def count_users() -> int:
    with _lock:
        return len(_get_users_cache())


def save_user(user_id, user_data):
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False
        users[user_id] = user_data
        _save_users(users)
        return True


def get_banned_users():
    with _lock:
        users = _get_users_cache()
        banned = []
        for user_id, user_data in users.items():
            if "banned" in user_data.get("roles", []):
                banned.append(user_data.get("username", user_id))
        return banned


def is_user_banned(user_id):
    user = get_user(user_id)
    return user and "banned" in user.get("roles", [])


def ban_user(user_id):
    with _lock:
        users = _get_users_cache()
        if user_id in users and "banned" not in users[user_id].get("roles", []):
            users[user_id].setdefault("roles", []).insert(0, "banned")
            _save_users(users)
            return True
        return False


def unban_user(user_id):
    with _lock:
        users = _get_users_cache()
        if user_id in users and "banned" in users[user_id].get("roles", []):
            users[user_id]["roles"].remove("banned")
            _save_users(users)
            return True
        return False


def give_role(user_id, role):
    with _lock:
        users = _get_users_cache()
        if user_id in users:
            users[user_id].setdefault("roles", []).append(role)
            _save_users(users)
            return True
        return False


def set_user_roles(user_id, roles_list):
    with _lock:
        users = _get_users_cache()
        if user_id in users:
            users[user_id]["roles"] = roles_list
            _save_users(users)
            return True
        return False


def remove_role(user_id, role):
    with _lock:
        users = _get_users_cache()
        if user_id in users and role in users[user_id].get("roles", []):
            users[user_id]["roles"].remove(role)
            _save_users(users)
            return True
        return False


def remove_role_from_all_users(role):
    with _lock:
        users = _get_users_cache()
        changed = False
        for user_id, user_data in users.items():
            if role in user_data.get("roles", []):
                users[user_id]["roles"].remove(role)
                changed = True
        if changed:
            _save_users(users)


def remove_user_roles(user_id, roles_to_remove):
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False

        current_roles = users[user_id].get("roles", [])
        removed_any = False

        for role in roles_to_remove:
            if role in current_roles:
                current_roles.remove(role)
                removed_any = True

        if removed_any:
            users[user_id]["roles"] = current_roles
            _save_users(users)
            return True

        return False


def remove_user(user_id):
    with _lock:
        users = _get_users_cache()
        if user_id in users:
            del users[user_id]
            _save_users(users)
            return True
        return False


def get_id_by_username(username):
    with _lock:
        users = _get_users_cache()
        for user_id, user_data in users.items():
            if user_data.get("username", "").lower() == username.lower():
                return user_id
        return None


def get_username_by_id(user_id):
    user = get_user(user_id)
    if user:
        return user.get("username") or user_id
    return user_id


def update_user_username(user_id, new_username):
    with _lock:
        users = _get_users_cache()
        if user_id in users:
            users[user_id]["username"] = new_username
            _save_users(users)
            return True
        return False


def generate_validator(user_id):
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return None

        validator = secrets.token_urlsafe(32)
        users[user_id]["validator"] = validator
        _save_users(users)
        return validator


def get_validator(user_id):
    user = get_user(user_id)
    return user.get("validator") if user else None


def get_user_id_by_validator(validator_token):
    if not validator_token:
        return None
    with _lock:
        users = _get_users_cache()
        for user_id, user_data in users.items():
            if user_data.get("validator") == validator_token:
                return user_id
        return None


def get_usernames_by_role(role_name):
    with _lock:
        users = _get_users_cache()
        usernames = []
        for user_id, user_data in users.items():
            if role_name in user_data.get("roles", []):
                usernames.append(user_data.get("username", user_id))
        return usernames


def set_nickname(user_id, nickname):
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False
        users[user_id]["nickname"] = nickname
        _save_users(users)
        return True


def get_nickname(user_id):
    user = get_user(user_id)
    return user.get("nickname") if user else None


def clear_nickname(user_id):
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False
        if "nickname" in users[user_id]:
            del users[user_id]["nickname"]
            _save_users(users)
        return True


def get_status(user_id) -> dict:
    user = get_user(user_id)
    if user:
        return user.get("status", DEFAULT_STATUS)
    return DEFAULT_STATUS


CRACKED_USER_PREFIX = "USR:local_"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def register_cracked_user(
    username: str, password: str, default_roles: list | None = None
) -> tuple[bool, str | None, str | None]:
    username = username.strip().lower()
    if not username or len(username) < 2 or len(username) > 32:
        return False, None, "Username must be 2-32 characters"
    if not password or len(password) < 4 or len(password) > 72:
        return False, None, "Password must be 4-72 characters"
    if not username.replace("_", "").replace("-", "").isalnum():
        return (
            False,
            None,
            "Username can only contain letters, numbers, hyphens, and underscores",
        )

    user_id = f"{CRACKED_USER_PREFIX}{username}"
    full_username = f"USR:local_{username}"

    with _lock:
        users = _get_users_cache()
        if user_id in users:
            return False, None, "Username already taken"

        for existing_id, existing_data in users.items():
            if existing_data.get("username", "").lower() == full_username.lower():
                return False, None, "Username already taken"

        password_hash = _hash_password(password)

        user_data = {
            "username": full_username,
            "nickname": username,
            "password_hash": password_hash,
            "roles": default_roles or ["user"],
            "status": DEFAULT_STATUS,
            "pfp_url": None,
        }
        users[user_id] = user_data
        _save_users(users)
        return True, user_id, None


def authenticate_cracked_user(
    username: str, password: str
) -> tuple[bool, str | None, str | None]:
    username = username.strip().lower()
    full_username = f"USR:local_{username}"

    with _lock:
        users = _get_users_cache()
        for user_id, user_data in users.items():
            if user_data.get("username", "").lower() == full_username.lower():
                if user_id.startswith(CRACKED_USER_PREFIX):
                    if _verify_password(password, user_data.get("password_hash", "")):
                        return True, user_id, None
                    return False, None, "Invalid password"
                return False, None, "This account uses Rotur authentication"
        return False, None, "User not found"


def set_pfp(user_id: str, pfp_url: str) -> bool:
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False
        users[user_id]["pfp_url"] = pfp_url
        _save_users(users)
        return True


def get_pfp(user_id: str) -> Optional[str]:
    user = get_user(user_id)
    return user.get("pfp_url") if user else None


def is_cracked_user(user_id: str) -> bool:
    return user_id.startswith(CRACKED_USER_PREFIX) if user_id else False


def set_status(user_id, status, text=None):
    if status not in ALLOWED_STATUSES:
        return False

    if text is not None and len(text) > 100:
        return False

    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False

        status_data = {"status": status, "text": text[:100] if text else ""}
        users[user_id]["status"] = status_data
        _save_users(users)
        return True
