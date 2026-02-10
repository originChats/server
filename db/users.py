import json, os
from . import roles
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

users_index = os.path.join(_MODULE_DIR, "users.json")
config = json.load(open(os.path.join(_MODULE_DIR, "..", "config.json"), "r"))

def user_exists(user_id):
    """
    Check if a user exists in the users database.
    """
    try:
        with open(users_index, "r") as f:
            users = json.load(f)
        return user_id in users
    except FileNotFoundError:
        return False

def get_user(user_id):
    """
    Get user data by user ID.
    """
    try:
        with open(users_index, "r") as f:
            users = json.load(f)
        return users.get(user_id, None)
    except FileNotFoundError:
        return None

def add_user(user_id, username=None):
    """
    Add a new user to the users database.
    """
    try:
        with open(users_index, "r") as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    if user_id in users:
        return False  # User already exists

    # Create user data with username
    user_data = config["DB"]["users"]["default"].copy()
    
    # If username is provided but different from ID (for backward compatibility)
    # or if user_data already has a username field from legacy data
    if username:
        user_data["username"] = username
    elif "username" not in user_data:
        user_data["username"] = user_id  # Legacy: ID was username
    
    users[user_id] = user_data

    with open(users_index, "w") as f:
        json.dump(users, f, indent=4)

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
    try:
        with open(users_index, "r") as f:
            users = json.load(f)

        for _, user_data in users.items():
            # Get the color of the first role
            user_roles = user_data.get("roles", [])
            color = None
            if user_roles:
                first_role_name = user_roles[0]
                first_role_data = roles.get_role(first_role_name)
                if first_role_data:
                    color = first_role_data.get("color")
            user_data["color"] = color

        user_arr = []
        for user_id, user_data in users.items():
            if "banned" in user_data.get("roles", []):
                continue
            # Use username field if available, otherwise fall back to user_id (legacy)
            username = user_data.get("username", user_id)
            user_arr.append({
                "username": username,
                "roles": user_data.get("roles", []),
                "color": user_data.get("color")
            })
        return user_arr
    except FileNotFoundError:
        return []
    
def save_user(user_id, user_data):
    """
    Save user data to the users database.
    """
    try:
        with open(users_index, "r") as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}

    users[user_id] = user_data

    with open(users_index, "w") as f:
        json.dump(users, f, indent=4)
    
def get_banned_users():
    """
    Get a list of all banned users.
    """
    try:
        with open(users_index, "r") as f:
            users_data = json.load(f)
        
        banned_users = []
        for user_id, user_data in users_data.items():
            if "banned" in user_data.get("roles", []):
                # Use username if available, otherwise fall back to ID
                username = user_data.get("username", user_id)
                banned_users.append(username)
        
        return banned_users
    except FileNotFoundError:
        return []

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
    user = get_user(user_id)
    if user:
        user["roles"].insert(0, role)
        save_user(user_id, user)
        return True
    return False

def remove_role(user_id, role):
    """
    Remove a role from a user.
    """
    user = get_user(user_id)
    if user:
        user["roles"].remove(role)
        save_user(user_id, user)
        return True
    return False

def remove_user(user_id):
    """
    Remove a user from the users database.
    """
    try:
        with open(users_index, "r") as f:
            users = json.load(f)

        users.pop(user_id, None)

        with open(users_index, "w") as f:
            json.dump(users, f, indent=4)
    except FileNotFoundError:
        return False
    return True

def get_id_by_username(username):
    """
    Get a user's ID by their username.
    """
    try:
        with open(users_index, "r") as f:
            users = json.load(f)
        
        username = username.lower()
        for user_id, user_data in users.items():
            if user_data.get("username", "").lower() == username:
                return user_id
        return None
    except FileNotFoundError:
        return None

def get_username_by_id(user_id):
    """
    Get a user's username by their ID.
    """
    user = get_user(user_id)
    if user:
        result = user.get("username", "")
        # Fallback: if username field is missing, use user_id (for legacy compatibility)
        if not result or result == "":
            return user_id
        return result
    return user_id  # Fallback to ID if user not found

def update_user_username(user_id, new_username):
    """
    Update a user's username. This handles username changes.
    """
    user = get_user(user_id)
    if user:
        user["username"] = new_username
        save_user(user_id, user)
        return True
    return False