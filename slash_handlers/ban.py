from db import users
from logger import Logger
from handlers.websocket_utils import disconnect_user
from slash_handlers.utils import (
    validate_target_user,
    check_can_modify_target,
    create_mod_response,
    disconnect_target_user,
    trigger_plugin_event,
    make_command_info
)


def get_command_info():
    return make_command_info(
        name="ban",
        description="Ban a user from the server",
        options=[
            {"name": "username", "description": "The user to ban", "type": "str", "required": True},
            {"name": "reason", "description": "Reason for the ban", "type": "str", "required": False}
        ],
        is_mod_command=True
    )


async def handle(ws, args, channel, server_data):
    target_username = args.get("username")
    reason = args.get("reason", "No reason provided")
    
    target_id, target_user, error = validate_target_user(target_username)
    if error:
        return error
    
    error = check_can_modify_target(target_user, "ban")
    if error:
        return error
    
    banned = users.ban_user(target_id)
    if not banned:
        return {"error": f"User '{target_username}' is already banned"}
    
    await disconnect_target_user(
        server_data.get("connected_clients", set()) if server_data else set(),
        target_username,
        "You have been banned",
        server_data
    )
    
    trigger_plugin_event(
        server_data.get("plugin_manager") if server_data else None,
        "user_ban", ws,
        {"user_id": target_id, "username": target_username, "reason": reason},
        server_data
    )
    
    Logger.info(f"User {target_username} banned by slash command. Reason: {reason}")
    
    return create_mod_response("🚫", target_username, "banned", reason)
