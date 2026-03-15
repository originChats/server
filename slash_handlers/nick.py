import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import users
from handlers.websocket_utils import broadcast_to_all
from logger import Logger


MAX_NICKNAME_LENGTH = 20


def get_command_info():
    return {
        "name": "nick",
        "description": "Set or clear your display nickname",
        "options": [
            {
                "name": "nickname",
                "description": "Your new nickname (leave empty to clear)",
                "type": "str",
                "required": False
            }
        ],
        "whitelistRoles": None,
        "blacklistRoles": None,
        "ephemeral": False
    }


async def handle(ws, args, channel, server_data):
    user_id = getattr(ws, "user_id", None)
    if not user_id:
        return {"error": "Not authenticated"}
    
    username = users.get_username_by_id(user_id)
    if not username:
        return {"error": "User not found"}
    
    nickname = args.get("nickname", "")
    
    if nickname:
        nickname = nickname.strip()
        
        if len(nickname) > MAX_NICKNAME_LENGTH:
            return {"error": f"Nickname too long (max {MAX_NICKNAME_LENGTH} characters)"}
        
        if not nickname:
            users.clear_nickname(user_id)
            await _broadcast_nickname_remove(server_data, user_id, username)
            return {"response": "Nickname cleared"}
        
        users.set_nickname(user_id, nickname)
        await _broadcast_nickname_update(server_data, user_id, username, nickname)
        
        Logger.info(f"User {username} set nickname to '{nickname}'")
        return {"response": f"Nickname set to **{nickname}**"}
    else:
        current_nickname = users.get_nickname(user_id)
        
        if current_nickname:
            users.clear_nickname(user_id)
            await _broadcast_nickname_remove(server_data, user_id, username)
            Logger.info(f"User {username} cleared their nickname")
            return {"response": "Nickname cleared"}
        else:
            return {"response": "You don't have a nickname set. Use `/nick <name>` to set one."}


async def _broadcast_nickname_update(server_data, user_id, username, nickname):
    if not server_data or "connected_clients" not in server_data:
        return
    
    msg = {
        "cmd": "nickname_update",
        "user": user_id,
        "username": username,
        "nickname": nickname
    }
    
    await broadcast_to_all(server_data["connected_clients"], msg)


async def _broadcast_nickname_remove(server_data, user_id, username):
    if not server_data or "connected_clients" not in server_data:
        return
    
    msg = {
        "cmd": "nickname_remove",
        "user": user_id,
        "username": username
    }
    
    await broadcast_to_all(server_data["connected_clients"], msg)
