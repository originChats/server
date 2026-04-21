from db import roles, users
from handlers.messages.helpers import _error, _require_user_id
from handlers.messages.audit import record
from handlers.websocket_utils import broadcast_to_all


async def handle_self_role_add(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    role_name = message.get("role")
    if not role_name:
        return _error("Role name is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    if not roles.is_role_self_assignable(role_name):
        return _error("This role is not self-assignable", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if role_name in user_roles:
        return _error("You already have this role", match_cmd)

    success = users.give_role(user_id, role_name)
    if not success:
        return _error("Failed to assign role", match_cmd)

    username = users.get_username_by_id(user_id)
    updated_roles = users.get_user_roles(user_id)
    color = roles.get_user_color(updated_roles)

    record("self_role_add", ws, target_id=user_id, target_name=username, details={"role": role_name})
    if server_data:
        server_data["plugin_manager"].trigger_event("self_role_add", ws, {
            "user_id": user_id,
            "username": username,
            "role_name": role_name
        }, server_data)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "user_roles_get",
            "user": username,
            "roles": updated_roles,
            "color": color
        }, server_data)

    return {
        "cmd": "self_role_add",
        "role": role_name,
        "success": True,
        "roles": updated_roles
    }


async def handle_self_role_remove(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    role_name = message.get("role")
    if not role_name:
        return _error("Role name is required", match_cmd)

    if not roles.role_exists(role_name):
        return _error("Role not found", match_cmd)

    if not roles.is_role_self_assignable(role_name):
        return _error("This role is not self-assignable", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if role_name not in user_roles:
        return _error("You don't have this role", match_cmd)

    success = users.remove_role(user_id, role_name)
    if not success:
        return _error("Failed to remove role", match_cmd)

    username = users.get_username_by_id(user_id)
    updated_roles = users.get_user_roles(user_id)
    color = roles.get_user_color(updated_roles)

    record("self_role_remove", ws, target_id=user_id, target_name=username, details={"role": role_name})
    if server_data:
        server_data["plugin_manager"].trigger_event("self_role_remove", ws, {
            "user_id": user_id,
            "username": username,
            "role_name": role_name
        }, server_data)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "user_roles_get",
            "user": username,
            "roles": updated_roles,
            "color": color
        }, server_data)

    return {
        "cmd": "self_role_remove",
        "role": role_name,
        "success": True,
        "roles": updated_roles
    }


async def handle_self_roles_list(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    self_assignable_roles = roles.get_self_assignable_roles()
    user_roles = users.get_user_roles(user_id)

    role_list = []
    for role_data in self_assignable_roles.values():
        role_list.append({
            **role_data,
            "assigned": role_data["name"] in user_roles
        })

    return {
        "cmd": "self_roles_list",
        "roles": role_list
    }
