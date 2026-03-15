import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import users, roles as role_db
from logger import Logger


def get_command_info():
    return {
        "name": "role",
        "description": "Add or remove a role from a user",
        "options": [
            {
                "name": "action",
                "description": "add or remove",
                "type": "enum",
                "choices": ["add", "remove"],
                "required": True
            },
            {
                "name": "username",
                "description": "The target user",
                "type": "str",
                "required": True
            },
            {
                "name": "role",
                "description": "The role to add or remove",
                "type": "str",
                "required": True
            }
        ],
        "whitelistRoles": ["owner"],
        "blacklistRoles": None,
        "ephemeral": False
    }


async def handle(ws, args, channel, server_data):
    action = args.get("action", "").lower()
    target_username = args.get("username")
    role_name = args.get("role")
    
    if not action:
        return {"error": "Action is required (add or remove)"}
    
    if action not in ["add", "remove"]:
        return {"error": "Action must be 'add' or 'remove'"}
    
    if not target_username:
        return {"error": "Username is required"}
    
    if not role_name:
        return {"error": "Role is required"}
    
    target_id = users.get_id_by_username(target_username)
    if not target_id:
        return {"error": f"User '{target_username}' not found"}
    
    if not role_db.role_exists(role_name):
        return {"error": f"Role '{role_name}' does not exist"}
    
    protected_roles = ["owner", "admin", "user", "banned"]
    user_roles = users.get_user_roles(ws.user_id) if hasattr(ws, "user_id") else []
    
    if action == "add":
        if role_name == "owner" and "owner" not in user_roles:
            return {"error": "Only the owner can assign the owner role"}
        
        users.give_role(target_id, role_name)
        Logger.info(f"Role '{role_name}' added to {target_username} by slash command")
        
        if server_data and "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event("user_roles_add", ws, {
                "user_id": target_id,
                "username": target_username,
                "roles": [role_name]
            }, server_data)
        
        return {"response": f"✅ Role **{role_name}** added to **{target_username}**."}
    
    else:
        if role_name == "user":
            return {"error": "Cannot remove the 'user' role"}
        
        target_user = users.get_user(target_id)
        if target_user:
            current_roles = target_user.get("roles", [])
            if len(current_roles) <= 1:
                return {"error": "Cannot remove the user's last role"}
        
        users.remove_role(target_id, role_name)
        Logger.info(f"Role '{role_name}' removed from {target_username} by slash command")
        
        if server_data and "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event("user_roles_remove", ws, {
                "user_id": target_id,
                "username": target_username,
                "roles": [role_name]
            }, server_data)
        
        return {"response": f"✅ Role **{role_name}** removed from **{target_username}**."}
