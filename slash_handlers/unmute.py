from db import users
from logger import Logger
from slash_handlers.utils import (
    validate_target_user,
    create_mod_response,
    make_command_info
)


def get_command_info():
    return make_command_info(
        name="unmute",
        description="Remove timeout from a user",
        options=[
            {"name": "username", "description": "The user to unmute", "type": "str", "required": True}
        ],
        is_mod_command=True
    )


async def handle(ws, args, channel, server_data):
    target_username = args.get("username")
    
    target_id, _, error = validate_target_user(target_username)
    if error:
        return error
    
    if not server_data or not server_data.get("rate_limiter"):
        return {"error": "Rate limiter not available"}
    
    rate_limiter = server_data["rate_limiter"]
    rate_limiter.reset_user(target_id)
    
    Logger.info(f"User {target_username} unmuted by slash command")
    
    return create_mod_response("🔊", target_username, "unmuted")
