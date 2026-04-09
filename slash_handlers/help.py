from slash_handlers import SERVER_SLASH_HANDLERS
from handlers.websocket_utils import _get_ws_attr
from handlers.helpers.validation import check_role_permission
from slash_handlers.utils import make_command_info


def get_command_info():
    return make_command_info(
        name="help",
        description="List all available slash commands",
        options=[],
        is_mod_command=False
    )


def _get_server_commands(user_roles):
    available = []
    for cmd_name, handler_data in SERVER_SLASH_HANDLERS.items():
        info = handler_data["info"]
        if check_role_permission(
            info.get("whitelistRoles"),
            info.get("blacklistRoles"),
            user_roles
        ):
            available.append({
                "name": cmd_name,
                "description": info.get("description", "No description")
            })
    return available


def _get_client_commands(server_data, user_roles):
    if not server_data or "slash_commands" not in server_data:
        return []
    
    available = []
    slash_commands = server_data["slash_commands"]
    
    for ws_id, commands in slash_commands.items():
        for cmd_name, cmd_data in commands.items():
            if cmd_name in SERVER_SLASH_HANDLERS or cmd_name.startswith("server_"):
                continue
            
            command_obj = cmd_data["command"]
            if not command_obj:
                continue
            
            if check_role_permission(
                getattr(command_obj, "whitelistRoles", None),
                getattr(command_obj, "blacklistRoles", None),
                user_roles
            ):
                available.append({
                    "name": cmd_name,
                    "description": getattr(command_obj, "description", "No description")
                })
    
    return available


async def handle(ws, args, channel, server_data):
    user_id = _get_ws_attr(ws, server_data, "user_id")
    user_roles = []
    
    if server_data and "connected_clients" in server_data:
        from db import users
        user_roles = users.get_user_roles(user_id) if user_id else []
    
    available_commands = _get_server_commands(user_roles)
    available_commands.extend(_get_client_commands(server_data, user_roles))
    available_commands.sort(key=lambda x: x["name"])
    
    if not available_commands:
        return {"response": "No commands available"}
    
    lines = ["**Available Commands:**"]
    for cmd in available_commands:
        lines.append(f"• `/{cmd['name']}` - {cmd['description']}")
    
    return {"response": "\n".join(lines)}
