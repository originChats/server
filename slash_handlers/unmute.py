import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import users
from logger import Logger


def get_command_info():
    return {
        "name": "unmute",
        "description": "Remove timeout from a user",
        "options": [
            {
                "name": "username",
                "description": "The user to unmute",
                "type": "str",
                "required": True
            }
        ],
        "whitelistRoles": ["admin", "owner"],
        "blacklistRoles": None,
        "ephemeral": False
    }


async def handle(ws, args, channel, server_data):
    target_username = args.get("username")
    
    if not target_username:
        return {"error": "Username is required"}
    
    target_id = users.get_id_by_username(target_username)
    if not target_id:
        return {"error": f"User '{target_username}' not found"}
    
    if not server_data or not server_data.get("rate_limiter"):
        return {"error": "Rate limiter not available"}
    
    rate_limiter = server_data["rate_limiter"]
    rate_limiter.reset_user(target_id)
    
    Logger.info(f"User {target_username} unmuted by slash command")
    
    return {"response": f"🔊 **{target_username}** has been unmuted."}
