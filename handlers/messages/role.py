from db import roles, users, channels
from handlers.messages.helpers import _error, _require_user_id, _require_user_roles


def handle_role_create(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    role_name = message.get("name")
    if not role_name:
        return _error("Role name is required", match_cmd)

    role_data = {}
    if message.get("description"):
        role_data["description"] = message["description"]
    if message.get("color"):
        role_data["color"] = message["color"]
    if message.get("permissions"):
        role_data["permissions"] = message["permissions"]
    if message.get("hoisted") is not None:
        role_data["hoisted"] = message["hoisted"]

    if roles.role_exists(role_name):
        return _error("Role already exists", match_cmd)

    created = roles.add_role(role_name, role_data)
    if server_data:
        server_data["plugin_manager"].trigger_event("role_create", ws, {
            "role_name": role_name,
            "description": message.get("description", ""),
            "color": message.get("color")
        }, server_data)

    return {"cmd": "role_create", "name": role_name, "created": created, "roles": roles.get_all_roles()}


def handle_role_update(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    if not server_data:
        return _error("Server data not available", match_cmd)
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    role_name = message.get("name")
    if not role_name:
        return _error("Role name is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    role_data = roles.get_role(role_name)
    if not role_data:
        return _error("Role not found", match_cmd)

    if message.get("description") is not None:
        role_data["description"] = message["description"]
    if message.get("color") is not None:
        role_data["color"] = message["color"]
    if message.get("hoisted") is not None:
        role_data["hoisted"] = message["hoisted"]

    updated = roles.update_role(role_name, role_data)
    if server_data:
        server_data["plugin_manager"].trigger_event("role_update", ws, {
            "role_name": role_name,
            "description": role_data.get("description", ""),
            "color": role_data.get("color")
        }, server_data)

    return {"cmd": "role_update", "name": role_name, "updated": updated, "roles": roles.get_all_roles()}


def handle_role_set(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    role_name = message.get("name")
    if not role_name:
        return _error("Role name is required", match_cmd)

    role_data = message.get("data")
    if not role_data or not isinstance(role_data, dict):
        return _error("Role data is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    updated = roles.update_role(role_name, role_data)
    if server_data:
        server_data["plugin_manager"].trigger_event("role_update", ws, {
            "role_name": role_name,
            "description": role_data.get("description", ""),
            "color": role_data.get("color")
        }, server_data)

    return {"cmd": "role_set", "name": role_name, "updated": updated, "roles": roles.get_all_roles()}


def handle_role_delete(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    role_name = message.get("name")
    if not role_name:
        return _error("Role name is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    if role_name in ["owner", "admin", "user"]:
        return _error("Cannot delete system roles", match_cmd)

    all_users = users.get_users()
    for user in all_users:
        if role_name in user.get("roles", []):
            return _error(f"Role is assigned to user '{user.get('username')}'", match_cmd)

    all_channels = channels.get_channels()
    for channel in all_channels:
        perms = channel.get("permissions", {})
        for perm_type, perm_roles in perms.items():
            if isinstance(perm_roles, list) and role_name in perm_roles:
                return _error(f"Role is used in channel '{channel.get('name')}' permissions", match_cmd)

    deleted = roles.delete_role(role_name)
    if server_data:
        server_data["plugin_manager"].trigger_event("role_delete", ws, {
            "role_name": role_name
        }, server_data)

    return {"cmd": "role_delete", "name": role_name, "deleted": deleted}


def handle_roles_list(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    all_roles = roles.get_all_roles()
    return {"cmd": "roles_list", "roles": all_roles}


def handle_role_permissions_set(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    role_name = message.get("name")
    if not role_name:
        return _error("Role name is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    permissions = message.get("permissions")
    if not isinstance(permissions, dict):
        return _error("Permissions must be an object", match_cmd)

    role_data = roles.get_role(role_name)
    if not role_data:
        return _error("Role not found", match_cmd)
    role_data["permissions"] = permissions
    updated = roles.update_role(role_name, role_data)

    return {"cmd": "role_permissions_set", "name": role_name, "permissions": permissions, "updated": updated}


def handle_role_permissions_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    role_name = message.get("name")
    if not role_name:
        return _error("Role name is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    role_perms = roles.get_role_permissions(role_name)
    return {"cmd": "role_permissions_get", "name": role_name, "permissions": role_perms}