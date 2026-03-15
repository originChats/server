import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import users
from logger import Logger


def get_command_info():
    return {
        "name": "unban",
        "description": "Unban a user from the server",
        "options": [
            {
                "name": "username",
                "description": "The user to unban",
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
    
    unbanned = users.unban_user(target_id)
    if not unbanned:
        return {"error": f"User '{target_username}' is not banned"}
    
    if server_data and "plugin_manager" in server_data:
        server_data["plugin_manager"].trigger_event("user_unban", ws, {
            "user_id": target_id,
            "username": target_username
        }, server_data)
    
    Logger.info(f"User {target_username} unbanned by slash command")
    
    return {"response": f"✅ **{target_username}** has been unbanned."}
