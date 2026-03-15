import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import channels
from logger import Logger


def get_command_info():
    return {
        "name": "channel",
        "description": "Create or delete a channel",
        "options": [
            {
                "name": "action",
                "description": "create or delete",
                "type": "enum",
                "choices": ["create", "delete"],
                "required": True
            },
            {
                "name": "name",
                "description": "The channel name",
                "type": "str",
                "required": True
            },
            {
                "name": "type",
                "description": "Channel type (text or voice) for create",
                "type": "enum",
                "choices": ["text", "voice"],
                "required": False
            }
        ],
        "whitelistRoles": ["owner"],
        "blacklistRoles": None,
        "ephemeral": False
    }


async def handle(ws, args, channel, server_data):
    action = args.get("action", "").lower()
    channel_name = args.get("name")
    channel_type = args.get("type", "text").lower()
    
    if not action:
        return {"error": "Action is required (create or delete)"}
    
    if action not in ["create", "delete"]:
        return {"error": "Action must be 'create' or 'delete'"}
    
    if not channel_name:
        return {"error": "Channel name is required"}
    
    if action == "create":
        if channel_type not in ["text", "voice"]:
            return {"error": "Channel type must be 'text' or 'voice'"}
        
        if channels.channel_exists(channel_name):
            return {"error": f"Channel '{channel_name}' already exists"}
        
        created = channels.create_channel(channel_name, channel_type)
        if not created:
            return {"error": "Failed to create channel"}
        
        channel_data = channels.get_channel(channel_name)
        
        if server_data and "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event("channel_create", ws, {
                "channel": channel_data
            }, server_data)
        
        Logger.info(f"Channel '{channel_name}' ({channel_type}) created by slash command")
        
        return {"response": f"✅ Channel **#{channel_name}** ({channel_type}) created."}
    
    else:
        if not channels.channel_exists(channel_name):
            return {"error": f"Channel '{channel_name}' not found"}
        
        current_channel = getattr(ws, "voice_channel", None)
        if current_channel == channel_name:
            return {"error": "Cannot delete the channel you are currently in"}
        
        deleted = channels.delete_channel(channel_name)
        if not deleted:
            return {"error": "Failed to delete channel"}
        
        if server_data and "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event("channel_delete", ws, {
                "channel_name": channel_name
            }, server_data)
        
        Logger.info(f"Channel '{channel_name}' deleted by slash command")
        
        return {"response": f"✅ Channel **#{channel_name}** deleted."}
