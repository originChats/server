import copy
import threading

from .database import init_db, execute, fetchone, fetchall, _json_dumps, _json_loads

_lock = threading.RLock()

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


def get_role(role_name):
    """Retrieve role data by role name."""
    init_db()
    
    row = fetchone("SELECT * FROM roles WHERE name = ?", (role_name,))
    if not row:
        return None
    
    return _process_role(row)

def count_roles() -> int:
    """Count roles in database."""
    init_db()

    ret = fetchone("SELECT COUNT(*) as cnt FROM roles")

    if ret is None:
        return 0
    return ret["cnt"]


def get_all_roles():
    """Retrieve all roles from the database, ordered by position."""
    init_db()

    rows = fetchall("SELECT * FROM roles ORDER BY position ASC, name ASC")
    return {row["name"]: _process_role(row) for row in rows}


def _process_role(row):
    """Convert database row to role dict."""
    return {
        "name": row["name"],
        "description": row.get("description"),
        "color": row.get("color"),
        "hoisted": bool(row.get("hoisted", 0)),
        "permissions": _json_loads(row.get("permissions")) or {},
        "self_assignable": bool(row.get("self_assignable", 0)),
        "category": row.get("category"),
        "position": row.get("position", 0) or 0
    }


def add_role(role_name, role_data):
    """Add a new role to the database."""
    init_db()
    
    with _lock:
        existing = fetchone("SELECT name FROM roles WHERE name = ?", (role_name,))
        if existing:
            return False
        
        execute(
            "INSERT INTO roles (name, description, color, hoisted, permissions, self_assignable, category) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (role_name,
             role_data.get("description"),
             role_data.get("color"),
             1 if role_data.get("hoisted") else 0,
             _json_dumps(role_data.get("permissions", {})),
             1 if role_data.get("self_assignable") else 0,
             role_data.get("category"))
        )
        return True


def update_role(role_name, role_data):
    """Update an existing role in the database."""
    init_db()
    
    with _lock:
        existing = fetchone("SELECT name FROM roles WHERE name = ?", (role_name,))
        if not existing:
            return False
        
        execute(
            "UPDATE roles SET description = ?, color = ?, hoisted = ?, permissions = ?, self_assignable = ?, category = ? WHERE name = ?",
            (role_data.get("description"),
             role_data.get("color"),
             1 if role_data.get("hoisted") else 0,
             _json_dumps(role_data.get("permissions", {})),
             1 if role_data.get("self_assignable") else 0,
             role_data.get("category"),
             role_name)
        )
        return True


def update_role_key(role_name, key, value):
    """Update a specific key in a role's data."""
    init_db()
    
    with _lock:
        role = fetchone("SELECT * FROM roles WHERE name = ?", (role_name,))
        if not role:
            return False
        
        role_data = _process_role(role)
        role_data[key] = value
        
        return update_role(role_name, role_data)


def delete_role(role_name):
    """Delete a role from the database."""
    init_db()
    
    with _lock:
        result = execute("DELETE FROM roles WHERE name = ?", (role_name,))
        return result.rowcount > 0


def role_exists(role_name):
    """Check if a role exists in the database."""
    init_db()
    
    row = fetchone("SELECT name FROM roles WHERE name = ?", (role_name,))
    return row is not None


def add_role_permission(role_name, permission, value=True):
    """Add or update a permission for a role."""
    init_db()
    
    with _lock:
        role = fetchone("SELECT * FROM roles WHERE name = ?", (role_name,))
        if not role:
            return False
        
        permissions = _json_loads(role.get("permissions")) or {}
        permissions[permission] = value
        
        execute(
            "UPDATE roles SET permissions = ? WHERE name = ?",
            (_json_dumps(permissions), role_name)
        )
        return True


def get_role_permissions(role_name):
    """Get all permissions for a role."""
    role_data = get_role(role_name)
    if role_data is None:
        return None
    return role_data.get("permissions", {})


def remove_role_permission(role_name, permission):
    """Remove a permission from a role."""
    init_db()
    
    with _lock:
        role = fetchone("SELECT * FROM roles WHERE name = ?", (role_name,))
        if not role:
            return False
        
        permissions = _json_loads(role.get("permissions")) or {}
        if permission not in permissions:
            return False
        
        del permissions[permission]
        execute(
            "UPDATE roles SET permissions = ? WHERE name = ?",
            (_json_dumps(permissions), role_name)
        )
        return True


def can_role_mention_role(user_roles, target_role):
    """Check if users with the given roles can mention the target role."""
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
    """Get all roles that are hoisted (displayed prominently)."""
    init_db()
    
    rows = fetchall("SELECT * FROM roles WHERE hoisted = 1")
    return [{"name": row["name"], **_process_role(row)} for row in rows]


def is_role_hoisted(role_name):
    """Check if a role is hoisted."""
    role_data = get_role(role_name)
    if role_data is None:
        return False
    return role_data.get("hoisted", False)


def is_role_self_assignable(role_name):
    """Check if a role is self-assignable."""
    role_data = get_role(role_name)
    if role_data is None:
        return False
    return role_data.get("self_assignable", False)


def get_self_assignable_roles():
    """Get all roles that are self-assignable."""
    init_db()
    
    rows = fetchall("SELECT * FROM roles")
    result = {}
    for row in rows:
        role_data = _process_role(row)
        if role_data.get("self_assignable", False):
            result[row["name"]] = role_data
    return result


def set_role_self_assignable(role_name, value):
    """Set whether a role is self-assignable."""
    init_db()
    
    with _lock:
        role = fetchone("SELECT * FROM roles WHERE name = ?", (role_name,))
        if not role:
            return False
        
        role_data = _process_role(role)
        role_data["self_assignable"] = value
        
        execute(
            "UPDATE roles SET description = ?, color = ?, hoisted = ?, permissions = ? WHERE name = ?",
            (role_data.get("description"),
             role_data.get("color"),
             1 if role_data.get("hoisted") else 0,
             _json_dumps(role_data.get("permissions", {})),
             role_name)
        )
        return True


PROTECTED_ROLES = ["owner", "admin", "moderator"]


def can_be_self_assignable(role_name):
    """Check if a role can be made self-assignable."""
    return role_name not in PROTECTED_ROLES


def reload_roles():
    """Reload roles from database (no-op for SQLite, kept for compatibility)."""
    init_db()
    return get_all_roles()


def reorder_roles(role_order):
    """Reorder roles by updating their positions."""
    init_db()

    with _lock:
        for i, role_name in enumerate(role_order):
            if not role_exists(role_name):
                return False
            execute(
                "UPDATE roles SET position = ? WHERE name = ?",
                (i, role_name)
            )
        return True
