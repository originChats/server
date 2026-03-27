import copy
import json
import os
import secrets
import threading
from typing import Dict, Optional
from . import roles
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger
from config_store import get_config_value
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

users_index = os.path.join(_MODULE_DIR, "users.json")
DEFAULT_USERS = {}

_lock = threading.RLock()

_users_cache: Dict[str, dict] = {}
_users_loaded: bool = False

def _load_users() -> Dict[str, dict]:
    global _users_cache, _users_loaded
    try:
        with open(users_index, "r") as f:
            _users_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _users_cache = {}
    _users_loaded = True
    return _users_cache

def _save_users(users_dict: Dict[str, dict]) -> None:
    global _users_cache, _users_loaded
    tmp = users_index + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users_dict, f, indent=4)
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
            json.dump(DEFAULT_USERS, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, users_index)

_ensure_storage()

def user_exists(user_id):
    """
    Check if a user exists in the users database.
    """
    with _lock:
        return user_id in _get_users_cache()

def get_user(user_id):
    """
    Get user data by user ID.
    """
    with _lock:
        user = _get_users_cache().get(user_id)
        return copy.deepcopy(user) if user is not None else None

def add_user(user_id, username=None):
    """
    Add a new user to the users database.
    """
    with _lock:
        users = _get_users_cache()

        if user_id in users:
            return False

        user_data = get_config_value("DB", "users", "default", default={}).copy()

        if username:
            user_data["username"] = username
        elif "username" not in user_data:
            user_data["username"] = user_id

        new_users = dict(users)
        new_users[user_id] = user_data
        _save_users(new_users)
    return True

def get_user_roles(user_id):
    """
    Get the roles of a user.
    """
    user = get_user(user_id)
    if user:
        return user.get("roles", [])
    return []


def get_users():
    """
    Get all users from the users database.
    """
    with _lock:
        users = _get_users_cache()

        user_arr = []
        for user_id, user_data in users.items():
            if "banned" in user_data.get("roles", []):
                continue

            user_roles = user_data.get("roles", [])
            color = None
            if user_roles:
                first_role_name = user_roles[0]
                first_role_data = roles.get_role(first_role_name)
                if first_role_data:
                    color = first_role_data.get("color")

            user_status = get_status(user_id)

            username = user_data.get("username", user_id)
            nickname = user_data.get("nickname")
            user_arr.append({
                "username": username,
                "nickname": nickname,
                "roles": list(user_roles),
                "color": color,
                "status": user_status
            })
    return user_arr

def save_user(user_id, user_data):
    """
    Save user data to the users database.
    """
    with _lock:
        new_users = dict(_get_users_cache())
        new_users[user_id] = user_data
        _save_users(new_users)

def get_banned_users():
    """
    Get a list of all banned users.
    """
    with _lock:
        users = _get_users_cache()
        banned = []
        for user_id, user_data in users.items():
            if "banned" in user_data.get("roles", []):
                username = user_data.get("username", user_id)
                banned.append(username)
    return banned

def is_user_banned(user_id):
    """
    Check if a user is banned by checking if they have the 'banned' role.
    """
    user = get_user(user_id)
    if user and "banned" in user.get("roles", []):
        return True
    return False

def ban_user(user_id):
    """
    Ban a user by giving them the 'banned' role.
    """
    with _lock:
        user = get_user(user_id)
        if user and "banned" not in user.get("roles", []):
            user["roles"].insert(0, "banned")
            save_user(user_id, user)
            return True
    return False

def unban_user(user_id):
    """
    Unban a user by removing the 'banned' role.
    """
    with _lock:
        user = get_user(user_id)
        if user and "banned" in user["roles"]:
            user["roles"].remove("banned")
            save_user(user_id, user)
            return True
    return False

def give_role(user_id, role):
    """
    Give a user a role.
    """
    with _lock:
        user = get_user(user_id)
        if user:
            user["roles"].append(role)
            save_user(user_id, user)
            return True
        return False

def set_user_roles(user_id, roles):
    """
    Set the exact roles for a user.

    Args:
        user_id (str): The ID of the user.
        roles (list): A list of roles to set as the user's roles.

    Returns:
        bool: True if roles were set successfully, False otherwise.
    """
    with _lock:
        user = get_user(user_id)
        if user:
            user["roles"] = roles
            save_user(user_id, user)
            return True
        return False

def remove_role(user_id, role):
    """
    Remove a role from a user.
    """
    with _lock:
        user = get_user(user_id)
        if user:
            if role in user["roles"]:
                user["roles"].remove(role)
                save_user(user_id, user)
                return True
    return False

def remove_user_roles(user_id, roles_to_remove):
    """
    Remove multiple roles from a user.

    Args:
        user_id (str): The ID of the user.
        roles_to_remove (list): A list of roles to remove.

    Returns:
        bool: True if at least one role was removed, False otherwise.
    """
    with _lock:
        user = get_user(user_id)
        if not user:
            return False

        current_roles = user.get("roles", [])
        removed_any = False

        for role in roles_to_remove:
            if role in current_roles:
                current_roles.remove(role)
                removed_any = True

        if removed_any:
            user["roles"] = current_roles
            save_user(user_id, user)
            return True

    return False

def remove_user(user_id):
    """
    Remove a user from the users database.
    """
    with _lock:
        users = _get_users_cache()
        if user_id not in users:
            return False
        new_users = dict(users)
        new_users.pop(user_id, None)
        _save_users(new_users)
    return True

def get_id_by_username(username):
    """
    Get a user's ID by their username.
    """
    with _lock:
        users = _get_users_cache()
        username_lower = username.lower()
        for user_id, user_data in users.items():
            if user_data.get("username", "").lower() == username_lower:
                return user_id
    return None

def get_username_by_id(user_id):
    """
    Get a user's username by their ID.
    """
    user = get_user(user_id)
    if user:
        result = user.get("username", "")
        if not result:
            return user_id
        return result
    return user_id


def update_user_username(user_id, new_username):
    """
    Update a user's username. This handles username changes.
    """
    with _lock:
        user = get_user(user_id)
        if user:
            user["username"] = new_username
            save_user(user_id, user)
            return True
    return False

def generate_validator(user_id):
    """
    Generate a new random validator token for a user and store it.
    Called every time a user connects so they always receive a fresh token.

    Args:
        user_id (str): The ID of the user.

    Returns:
        str: The generated validator token, or None if the user does not exist.
    """
    with _lock:
        user = get_user(user_id)
        if not user:
            return None

        validator = secrets.token_urlsafe(32)
        user["validator"] = validator
        save_user(user_id, user)
    return validator

def get_validator(user_id):
    """
    Get the stored validator token for a user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        str: The validator token, or None if the user or token does not exist.
    """
    user = get_user(user_id)
    if not user:
        return None
    return user.get("validator")


def get_user_id_by_validator(validator_token):
    """
    Get a user's ID by their validator token.

    Args:
        validator_token (str): The validator token to search for.

    Returns:
        str: The user ID, or None if not found.
    """
    if not validator_token:
        return None
    with _lock:
        users = _get_users_cache()
        for user_id, user_data in users.items():
            if user_data.get("validator") == validator_token:
                return user_id
    return None


def get_usernames_by_role(role_name):
    """
    Get all usernames that have a specific role.

    Args:
        role_name (str): The name of the role to search for.

    Returns:
        list: A list of usernames that have the specified role.
    """
    with _lock:
        users = _get_users_cache()
        usernames = []
        for user_id, user_data in users.items():
            if role_name in user_data.get("roles", []):
                username = user_data.get("username", user_id)
                usernames.append(username)
        return usernames


def set_nickname(user_id, nickname):
    """
    Set a user's display nickname.

    Args:
        user_id (str): The ID of the user.
        nickname (str): The nickname to set.

    Returns:
        bool: True if successful, False if user not found.
    """
    with _lock:
        user = get_user(user_id)
        if not user:
            return False
        user["nickname"] = nickname
        save_user(user_id, user)
        return True


def get_nickname(user_id):
    """
    Get a user's nickname.

    Args:
        user_id (str): The ID of the user.

    Returns:
        str or None: The nickname if set, None otherwise.
    """
    user = get_user(user_id)
    if user:
        return user.get("nickname")
    return None


def clear_nickname(user_id):
    """
    Clear a user's nickname.

    Args:
        user_id (str): The ID of the user.

    Returns:
        bool: True if successful, False if user not found.
    """
    with _lock:
        user = get_user(user_id)
        if not user:
            return False
        if "nickname" in user:
            del user["nickname"]
            save_user(user_id, user)
        return True


ALLOWED_STATUSES = ["online", "idle", "dnd", "offline"]

DEFAULT_STATUS = {
    "status": "online",
    "text": ""
}

def get_status(user_id) -> dict:
    """
    Get a user's status.

    Args:
        user_id (str): The ID of the user.

    Returns:
        str: The user's status, defaults to "online" if not set.
    """
    user = get_user(user_id)
    if user:
        return user.get("status", DEFAULT_STATUS)
    return DEFAULT_STATUS

def set_status(user_id, status, text=None):
    """
    Set a user's status.

    Args:
        user_id (str): The ID of the user.
        status (str): The status to set. Must be one of: online, idle, dnd, offline.
        text (str, optional): A custom status message (max 100 characters).

    Returns:
        bool: True if successful, False if user not found or invalid status.
    """
    if status not in ALLOWED_STATUSES:
        return False

    if text is not None and len(text) > 100:
        return False

    with _lock:
        user = get_user(user_id)
        if not user:
            return False
        user["status"] = {
            "status": status,
            "text": text[:100] if text else ""
        }
        save_user(user_id, user)
        return True
