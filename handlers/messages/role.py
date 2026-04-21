from db import roles, users, channels, permissions
from handlers.messages.helpers import _error, _require_user_id, _require_permission, _require_can_manage_role
from handlers.messages.audit import record
from handlers.websocket_utils import broadcast_to_all


async def handle_role_create(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_roles", match_cmd)
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
    if message.get("self_assignable") is not None:
        if message["self_assignable"] and not roles.can_be_self_assignable(role_name):
            return _error(f"Role '{role_name}' cannot be made self-assignable", match_cmd)
        role_data["self_assignable"] = message["self_assignable"]
    if "category" in message:
        role_data["category"] = message["category"]

    if roles.role_exists(role_name):
        return _error("Role already exists", match_cmd)

    role_id = roles.add_role(role_name, role_data)
    record("role_create", ws, target_id=role_id, target_name=role_name,
           details={"color": message.get("color"), "permissions": message.get("permissions")})
    if server_data:
        server_data["plugin_manager"].trigger_event("role_create", ws, {
            "role_id": role_id,
            "role_name": role_name,
            "description": message.get("description", ""),
            "color": message.get("color")
        }, server_data)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "roles_list",
            "roles": roles.get_all_roles()
        }, server_data)
    return {"cmd": "role_create", "id": role_id, "name": role_name}


async def handle_role_reorder(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_roles", match_cmd)
    if error:
        return error

    if not server_data:
        return _error("Server data not available", match_cmd)

    role_order = message.get("roles")
    if not role_order or not isinstance(role_order, list):
        return _error("Roles array is required", match_cmd)

    if not roles.reorder_roles(role_order):
        return _error("Failed to reorder roles", match_cmd)

    record("role_reorder", ws, details={"roles": role_order})
    await broadcast_to_all(server_data["connected_clients"], {
        "cmd": "roles_list",
        "roles": roles.get_all_roles()
    }, server_data)

    return {"cmd": "role_reorder", "roles": role_order}


async def handle_role_update(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    if not server_data:
        return _error("Server data not available", match_cmd)
    error = _require_permission(user_id, "manage_roles", match_cmd)
    if error:
        return error

    role_id_or_name = message.get("id") or message.get("name")
    if not role_id_or_name:
        return _error("Role id or name is required", match_cmd)

    error = _require_can_manage_role(user_id, role_id_or_name, match_cmd)
    if error:
        return error

    if not roles.role_exists(role_id_or_name):
        return _error("Role not found", match_cmd)

    role_data = roles.get_role(role_id_or_name)
    if not role_data:
        return _error("Role not found", match_cmd)

    new_name = message.get("name")
    if new_name is not None and new_name != role_data.get("name"):
        old_name = role_data.get("name")
        all_channels = channels.get_channels()
        for channel in all_channels:
            perms = channel.get("permissions", {})
            for perm_type, perm_roles in perms.items():
                if isinstance(perm_roles, list) and old_name in perm_roles:
                    return _error(f"Cannot rename role: it is used in channel '{channel.get('name')}' permissions", match_cmd)
        role_data["name"] = new_name
    if message.get("description") is not None:
        role_data["description"] = message["description"]
    if "color" in message:
        role_data["color"] = message["color"]
    if message.get("hoisted") is not None:
        role_data["hoisted"] = message["hoisted"]
    if message.get("self_assignable") is not None:
        if message["self_assignable"] and not roles.can_be_self_assignable(role_id_or_name):
            return _error(f"Role '{role_data.get('name')}' cannot be made self-assignable", match_cmd)
        role_data["self_assignable"] = message["self_assignable"]
    if message.get("permissions") is not None:
        role_data["permissions"] = message["permissions"]
    if "category" in message:
        role_data["category"] = message["category"]

    updated = roles.update_role(role_id_or_name, role_data)
    record("role_update", ws, target_id=role_data.get("id"), target_name=role_data.get("name"),
           details={"color": role_data.get("color"), "permissions": role_data.get("permissions")})
    if server_data:
        server_data["plugin_manager"].trigger_event("role_update", ws, {
            "role_id": role_data.get("id"),
            "role_name": role_data.get("name"),
            "description": role_data.get("description", ""),
            "color": role_data.get("color")
        }, server_data)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "roles_list",
            "roles": roles.get_all_roles()
        }, server_data)
    return {"cmd": "role_update", "id": role_data.get("id"), "name": role_data.get("name"), "updated": updated}


async def handle_role_set(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_roles", match_cmd)
    if error:
        return error

    role_id_or_name = message.get("id") or message.get("name")
    if not role_id_or_name:
        return _error("Role id or name is required", match_cmd)

    error = _require_can_manage_role(user_id, role_id_or_name, match_cmd)
    if error:
        return error

    role_data = message.get("data")
    if not role_data or not isinstance(role_data, dict):
        return _error("Role data is required", match_cmd)

    if not roles.role_exists(role_id_or_name):
        return _error("Role not found", match_cmd)

    updated = roles.update_role(role_id_or_name, role_data)
    role = roles.get_role(role_id_or_name)

    if not role:
        return _error("Role not found after update", match_cmd)

    record("role_update", ws, target_id=role.get("id"), target_name=role.get("name"),
           details=role_data)
    if server_data:
        server_data["plugin_manager"].trigger_event("role_update", ws, {
            "role_id": role.get("id"),
            "role_name": role.get("name"),
            "description": role_data.get("description", ""),
            "color": role_data.get("color")
        }, server_data)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "roles_list",
            "roles": roles.get_all_roles()
        }, server_data)
    return {"cmd": "role_set", "id": role.get("id"), "name": role.get("name"), "updated": updated}


async def handle_role_delete(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_roles", match_cmd)
    if error:
        return error

    role_id_or_name = message.get("id") or message.get("name")
    if not role_id_or_name:
        return _error("Role id or name is required", match_cmd)

    role = roles.get_role(role_id_or_name)
    if not role:
        return _error("Role not found", match_cmd)

    error = _require_can_manage_role(user_id, role.get("name"), match_cmd)
    if error:
        return error

    role_name = role.get("name")

    if role_name in ["owner", "admin", "user"]:
        return _error("Cannot delete system roles", match_cmd)

    all_channels = channels.get_channels()
    for channel in all_channels:
        perms = channel.get("permissions", {})
        for perm_type, perm_roles in perms.items():
            if isinstance(perm_roles, list) and role_name in perm_roles:
                return _error(f"Role is used in channel '{channel.get('name')}' permissions", match_cmd)

    users.remove_role_from_all_users(role_name)

    deleted = roles.delete_role(role_id_or_name)
    record("role_delete", ws, target_id=role.get("id"), target_name=role_name)
    if server_data:
        server_data["plugin_manager"].trigger_event("role_delete", ws, {
            "role_id": role.get("id"),
            "role_name": role_name
        }, server_data)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "roles_list",
            "roles": roles.get_all_roles()
        }, server_data)
    return {"cmd": "role_delete", "id": role.get("id"), "name": role_name, "deleted": deleted}


def handle_roles_list(ws, message, match_cmd):
    _, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    all_roles = roles.get_all_roles()
    return {"cmd": "roles_list", "roles": all_roles}


def handle_role_permissions_set(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_roles", match_cmd)
    if error:
        return error

    role_id_or_name = message.get("id") or message.get("name")
    if not role_id_or_name:
        return _error("Role id or name is required", match_cmd)

    error = _require_can_manage_role(user_id, role_id_or_name, match_cmd)
    if error:
        return error

    if not roles.role_exists(role_id_or_name):
        return _error("Role not found", match_cmd)

    perms = message.get("permissions")
    if not isinstance(perms, list):
        return _error("Permissions must be an array", match_cmd)

    role_data = roles.get_role(role_id_or_name)
    if not role_data:
        return _error("Role not found", match_cmd)
    role_data["permissions"] = perms
    updated = roles.update_role(role_id_or_name, role_data)

    record("role_permissions_set", ws, target_id=role_data.get("id"), target_name=role_data.get("name"),
           details={"permissions": perms})
    return {"cmd": "role_permissions_set", "id": role_data.get("id"), "name": role_data.get("name"), "permissions": perms, "updated": updated}


async def handle_role_permissions_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    role_id_or_name = message.get("id") or message.get("name")
    if not role_id_or_name:
        return _error("Role id or name is required", match_cmd)

    if not roles.role_exists(role_id_or_name):
        return _error("Role not found", match_cmd)

    role_perms = roles.get_role_permissions(role_id_or_name)
    role = roles.get_role(role_id_or_name)
    if not role:
        return _error("Role not found", match_cmd)
    return {"cmd": "role_permissions_get", "id": role.get("id"), "name": role.get("name"), "permissions": role_perms}
