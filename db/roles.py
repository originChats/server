import json, os

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

def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(roles_index):
        with open(roles_index, "w") as f:
            json.dump(DEFAULT_ROLES, f, indent=4)

_ensure_storage()

def get_role(role_name):
    """
    Retrieve role data by role name.
    
    Args:
        role_name (str): The name of the role to retrieve.
    
    Returns:
        dict: The role data if found, None otherwise.
    """
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
        return roles.get(role_name, None)
    except FileNotFoundError:
        return None

def get_all_roles():
    """
    Retrieve all roles from the roles database.
    
    Returns:
        dict: A dictionary of all roles.
    """
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
        return roles
    except FileNotFoundError:
        return {}

def add_role(role_name, role_data):
    """
    Add a new role to the roles database.
    
    Args:
        role_name (str): The name of the role to add.
        role_data (dict): The data for the new role.
    
    Returns:
        bool: True if the role was added successfully, False if it already exists.
    """
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
    except FileNotFoundError:
        roles = {}

    if role_name in roles:
        return False  # Role already exists

    roles[role_name] = role_data

    with open(roles_index, "w") as f:
        json.dump(roles, f, indent=4)

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
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
    except FileNotFoundError:
        return False  # Roles database does not exist

    if role_name not in roles:
        return False  # Role does not exist

    roles[role_name] = role_data

    with open(roles_index, "w") as f:
        json.dump(roles, f, indent=4)

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
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
    except FileNotFoundError:
        return False  # Roles database does not exist

    if role_name not in roles:
        return False  # Role does not exist

    roles[role_name][key] = value

    with open(roles_index, "w") as f:
        json.dump(roles, f, indent=4)

    return True

def delete_role(role_name):
    """
    Delete a role from the roles database.
    
    Args:
        role_name (str): The name of the role to delete.
    
    Returns:
        bool: True if the role was deleted successfully, False if it does not exist.
    """
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
    except FileNotFoundError:
        return False  # Roles database does not exist

    if role_name not in roles:
        return False  # Role does not exist

    del roles[role_name]

    with open(roles_index, "w") as f:
        json.dump(roles, f, indent=4)

    return True

def role_exists(role_name):
    """
    Check if a role exists in the roles database.
    
    Args:
        role_name (str): The name of the role to check.
    
    Returns:
        bool: True if the role exists, False otherwise.
    """
    try:
        with open(roles_index, "r") as f:
            roles = json.load(f)
        return role_name in roles
    except FileNotFoundError:
        return False  # Roles database does not exist
