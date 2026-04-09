from db import users
from logger import Logger
from slash_handlers.utils import (
    validate_target_user,
    create_mod_response,
    trigger_plugin_event,
    make_command_info
)


def get_command_info():
    return make_command_info(
        name="unban",
        description="Unban a user from the server",
        options=[
            {"name": "username", "description": "The user to unban", "type": "str", "required": True}
        ],
        is_mod_command=True
    )


async def handle(ws, args, channel, server_data):
    target_username = args.get("username")
    
    target_id, _, error = validate_target_user(target_username)
    if error:
        return error
    
    unbanned = users.unban_user(target_id)
    if not unbanned:
        return {"error": f"User '{target_username}' is not banned"}
    
    trigger_plugin_event(
        server_data.get("plugin_manager") if server_data else None,
        "user_unban", ws,
        {"user_id": target_id, "username": target_username},
        server_data
    )
    
    Logger.info(f"User {target_username} unbanned by slash command")
    
    return create_mod_response("✅", target_username, "unbanned")
