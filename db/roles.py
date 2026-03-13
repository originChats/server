import copy
import json
import os
import threading

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

roles_index = os.path.join(_MODULE_DIR, "roles.json")
DEFAULT_ROLES = {
    "owner": {
        "description": "Server owner with ultimate permissions.",
        "color": "#9400D3"
    },
    "admin": {
        "description": "Administrator role with full permissions.",
        "color": "#FF0000"
    },
    "moderator": {
        "description": "Moderator role with elevated permissions.",
        "color": "#FFFF00"
    },
    "user": {
        "description": "Regular user role with standard permissions.",
        "color": "#FFFFFF"
    }
}

_lock = threading.RLock()

_roles_cache: dict = {}
_roles_loaded: bool = False

def _load_roles() -> dict:
    global _roles_cache, _roles_loaded
    try:
        with open(roles_index, "r") as f:
            _roles_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _roles_cache = copy.deepcopy(DEFAULT_ROLES)
    _roles_loaded = True
    return _roles_cache

def _save_roles(roles_dict: dict) -> None:
    global _roles_cache, _roles_loaded
    tmp = roles_index + ".tmp"
    with open(tmp, "w") as f:
        json.dump(roles_dict, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, roles_index)
    _roles_cache = roles_dict
    _roles_loaded = True

def _get_roles_cache() -> dict:
    if not _roles_loaded:
        _load_roles()
    return _roles_cache

def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(roles_index):
        tmp = roles_index + ".tmp"
        with open(tmp, "w") as f:
            json.dump(DEFAULT_ROLES, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, roles_index)

_ensure_storage()

def get_role(role_name):
    """
    Retrieve role data by role name.
    
    Args:
        role_name (str): The name of the role to retrieve.
    
    Returns:
        dict: The role data if found, None otherwise.
    """
    with _lock:
        role = _get_roles_cache().get(role_name)
        return copy.deepcopy(role) if role is not None else None

def get_all_roles():
    """
    Retrieve all roles from the roles database.
    
    Returns:
        dict: A dictionary of all roles.
    """
    with _lock:
        return copy.deepcopy(_get_roles_cache())

def add_role(role_name, role_data):
    """
    Add a new role to the roles database.
    
    Args:
        role_name (str): The name of the role to add.
        role_data (dict): The data for the new role.
    
    Returns:
        bool: True if the role was added successfully, False if it already exists.
    """
    with _lock:
        roles = _get_roles_cache()
        if role_name in roles:
            return False
        new_roles = dict(roles)
        new_roles[role_name] = copy.deepcopy(role_data)
        _save_roles(new_roles)
    return True

def update_role(role_name, role_data):
    """
    Update an existing role in the roles database.
    
    Args:
        role_name (str): The name of the role to update.
        role_data (dict): The new data for the role.
    
    Returns:
        bool: True if the role was updated successfully, False if it does not exist.
    """
    with _lock:
        roles = _get_roles_cache()
        if role_name not in roles:
            return False
        new_roles = dict(roles)
        new_roles[role_name] = copy.deepcopy(role_data)
        _save_roles(new_roles)
    return True

def update_role_key(role_name, key, value):
    """
    Update a specific key in a role's data.
    
    Args:
        role_name (str): The name of the role to update.
        key (str): The key to update.
        value: The new value for the key.
    
    Returns:
        bool: True if the role was updated successfully, False if it does not exist.
    """
    with _lock:
        roles = _get_roles_cache()
        if role_name not in roles:
            return False
        new_roles = dict(roles)
        new_roles[role_name] = dict(new_roles[role_name])
        new_roles[role_name][key] = value
        _save_roles(new_roles)
    return True

def delete_role(role_name):
    """
    Delete a role from the roles database.
    
    Args:
        role_name (str): The name of the role to delete.
    
    Returns:
        bool: True if the role was deleted successfully, False if it does not exist.
    """
    with _lock:
        roles = _get_roles_cache()
        if role_name not in roles:
            return False
        new_roles = dict(roles)
        del new_roles[role_name]
        _save_roles(new_roles)
    return True

def role_exists(role_name):
    """
    Check if a role exists in the roles database.
    
    Args:
        role_name (str): The name of the role to check.
    
    Returns:
        bool: True if the role exists, False otherwise.
    """
    with _lock:
        return role_name in _get_roles_cache()

def add_role_permission(role_name, permission, value=True):
    """
    Add or update a permission for a role.
    
    Args:
        role_name (str): The name of the role.
        permission (str): The permission name (e.g., "mention_roles").
        value: The permission value.
    
    Returns:
        bool: True if the permission was set successfully, False otherwise.
    """
    with _lock:
        roles = _get_roles_cache()
        if role_name not in roles:
            return False
        new_roles = dict(roles)
        new_roles[role_name] = dict(new_roles[role_name])
        perms = dict(new_roles[role_name].get("permissions", {}))
        perms[permission] = value
        new_roles[role_name]["permissions"] = perms
        _save_roles(new_roles)
    return True

def get_role_permissions(role_name):
    """
    Get all permissions for a role.
    
    Args:
        role_name (str): The name of the role.
    
    Returns:
        dict: A dictionary of permissions for the role, or None if the role does not exist.
    """
    role_data = get_role(role_name)
    if role_data is None:
        return None
    return role_data.get("permissions", {})

def remove_role_permission(role_name, permission):
    """
    Remove a permission from a role.
    
    Args:
        role_name (str): The name of the role.
        permission (str): The permission name to remove.
    
    Returns:
        bool: True if the permission was removed, False otherwise.
    """
    with _lock:
        roles = _get_roles_cache()
        if role_name not in roles:
            return False
        if "permissions" in roles[role_name] and permission in roles[role_name]["permissions"]:
            new_roles = dict(roles)
            new_roles[role_name] = dict(new_roles[role_name])
            new_roles[role_name]["permissions"] = dict(new_roles[role_name]["permissions"])
            del new_roles[role_name]["permissions"][permission]
            _save_roles(new_roles)
            return True
    return False

def can_role_mention_role(user_roles, target_role):
    """
    Check if users with the given roles can mention the target role.
    
    Args:
        user_roles (list): List of roles the user has.
        target_role (str): The role being mentioned.
    
    Returns:
        bool: True if the user can mention the target role, False otherwise.
    """
    if "owner" in user_roles:
        return True
    
    target_role_data = get_role(target_role)
    if target_role_data is None:
        return True
    
    permissions = target_role_data.get("permissions", {})
    
    mention_permission = permissions.get("mention_roles")
    
    if mention_permission is None:
        return True
    
    if isinstance(mention_permission, str):
        return mention_permission in user_roles
    
    if isinstance(mention_permission, list):
        return any(role in user_roles for role in mention_permission)
    
    if isinstance(mention_permission, bool):
        return mention_permission
    
    return True

def get_hoisted_roles():
    """
    Get all roles that are hoisted (displayed prominently).
    
    Returns:
        list: A list of role data for hoisted roles.
    """
    with _lock:
        roles_dict = _get_roles_cache()
        hoisted_roles = []

        for role_name, role_data in roles_dict.items():
            if role_data.get("hoisted", False):
                hoisted_roles.append({
                    "name": role_name,
                    **copy.deepcopy(role_data)
                })

    return hoisted_roles

def is_role_hoisted(role_name):
    """
    Check if a role is hoisted.
    
    Args:
        role_name (str): The name of the role.
    
    Returns:
        bool: True if the role is hoisted, False otherwise.
    """
    role_data = get_role(role_name)
    if role_data is None:
        return False
    return role_data.get("hoisted", False)
