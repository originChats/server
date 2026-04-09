import asyncio
from db import users
from handlers.websocket_utils import send_to_client, _get_ws_attr
from logger import Logger
from slash_handlers.utils import (
    validate_target_user,
    check_can_modify_target,
    create_mod_response,
    make_command_info
)


def get_command_info():
    return make_command_info(
        name="mute",
        description="Timeout a user (prevent them from sending messages)",
        options=[
            {"name": "username", "description": "The user to mute", "type": "str", "required": True},
            {"name": "duration", "description": "Duration in seconds", "type": "int", "required": True},
            {"name": "reason", "description": "Reason for the mute", "type": "str", "required": False}
        ],
        is_mod_command=True
    )


async def handle(ws, args, channel, server_data):
    target_username = args.get("username")
    duration = args.get("duration")
    reason = args.get("reason", "No reason provided")
    
    if not duration:
        return {"error": "Duration is required"}
    
    try:
        duration = int(duration)
        if duration <= 0:
            return {"error": "Duration must be a positive number"}
    except (ValueError, TypeError):
        return {"error": "Duration must be a valid number"}
    
    target_id, target_user, error = validate_target_user(target_username)
    if error:
        return error
    
    error = check_can_modify_target(target_user, "mute")
    if error:
        return error
    
    if not server_data or not server_data.get("rate_limiter"):
        return {"error": "Rate limiter not available"}
    
    rate_limiter = server_data["rate_limiter"]
    rate_limiter.set_user_timeout(target_id, duration)
    
    connected_clients = server_data.get("connected_clients", set())
    target_ws = None
    for client in connected_clients:
        if _get_ws_attr(client, "user_id") == target_id:
            target_ws = client
            break
    
    if target_ws:
        loop = asyncio.get_event_loop()
        loop.create_task(send_to_client(target_ws, {
            "cmd": "rate_limit",
            "reason": f"Muted: {reason}",
            "length": duration * 1000
        }))
    
    Logger.info(f"User {target_username} muted for {duration}s by slash command. Reason: {reason}")
    
    return create_mod_response("🔇", target_username, f"muted for {duration} seconds", reason)
