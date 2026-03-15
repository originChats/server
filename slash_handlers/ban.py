import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import users
from logger import Logger


def get_command_info():
    return {
        "name": "ban",
        "description": "Ban a user from the server",
        "options": [
            {
                "name": "username",
                "description": "The user to ban",
                "type": "str",
                "required": True
            },
            {
                "name": "reason",
                "description": "Reason for the ban",
                "type": "str",
                "required": False
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
    
    reason = args.get("reason", "No reason provided")
    
    target_id = users.get_id_by_username(target_username)
    if not target_id:
        return {"error": f"User '{target_username}' not found"}
    
    target_user = users.get_user(target_id)
    if target_user:
        target_roles = target_user.get("roles", [])
        if "owner" in target_roles:
            return {"error": "Cannot ban the server owner"}
    
    banned = users.ban_user(target_id)
    if not banned:
        return {"error": f"User '{target_username}' is already banned"}
    
    if server_data and "plugin_manager" in server_data:
        server_data["plugin_manager"].trigger_event("user_ban", ws, {
            "user_id": target_id,
            "username": target_username,
            "reason": reason
        }, server_data)
    
    Logger.info(f"User {target_username} banned by slash command. Reason: {reason}")
    
    return {"response": f"🚫 **{target_username}** has been banned.\n**Reason:** {reason}"}
