import requests
from db import users, roles, push as push_db
from handlers.websocket_utils import send_to_client, broadcast_to_all, _get_ws_attr, _set_ws_attr
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger

async def handle_authentication(websocket, data, config_data, connected_clients, client_ip, server_data=None, validator_key=None):
    """Handle user authentication"""
    url = "https://api.rotur.dev/validate"
    key = validator_key
    validator = data.get("validator")

    # Validate with rotur service
    response = requests.get(url, params={"key": key, "v": validator}, timeout=5)
    if response.status_code != 200 or response.json().get("valid") != True:
        await send_to_client(websocket, {"cmd": "auth_error", "val": "Invalid authentication"})
        Logger.error(f"Client {client_ip} failed authentication")
        return False

    # Extract user ID and username from API response
    api_response = response.json()
    user_id = api_response.get("id", "")
    username = api_response.get("username", "")

    _set_ws_attr(websocket, "authenticated", True)
    _set_ws_attr(websocket, "user_id", user_id)
    _set_ws_attr(websocket, "username", username)

    user = users.get_user(user_id)
    if user:
        _set_ws_attr(websocket, "user_roles", user.get("roles", []))

    if users.is_user_banned(user_id):
        await send_to_client(websocket, {"cmd": "auth_error", "val": "Access denied: You are banned from this server"})
        Logger.warning(f"Banned user {username} (ID: {user_id}) attempted to connect from {client_ip}")
        _set_ws_attr(websocket, "authenticated", False)
        return False

    request = _get_ws_attr(websocket, "request")
    if request:
        headers = request.headers
        ip = headers.get("CF-Connecting-IP", "") or headers.get("X-Forwarded-For", "").split(",")[0].strip()
        user_agent = headers.get("User-Agent", "")
        country = headers.get("CF-IPCountry", "")
        device_fingerprint = push_db.compute_device_fingerprint(ip, user_agent, country)
        push_db.update_last_used(username, device_fingerprint)

    is_new_user = not users.user_exists(user_id)
    if is_new_user:
        users.add_user(user_id, username)
        Logger.add(f"User {username} (ID: {user_id}) created")
        _set_ws_attr(websocket, "user_roles", ["user"])
    elif user:
        _set_ws_attr(websocket, "user_roles", user.get("roles", []))

    existing_user = users.get_user(user_id)
    if existing_user and existing_user.get("username") != username:
        users.update_user_username(user_id, username)
        Logger.add(f"Updated username for ID {user_id} to {username}")

    await send_to_client(websocket, {"cmd": "auth_success", "val": "Authentication successful"})

    user = users.get_user(user_id)
    if not user:
        await send_to_client(websocket, {"cmd": "auth_error", "val": "User not found"})
        Logger.error(f"User {username} (ID: {user_id}) not found after authentication")
        return False

    user["username"] = username

    validator_token = users.generate_validator(user_id)

    user_for_client = {k: v for k, v in user.items() if k != "validator"}

    ready_payload = {
        "cmd": "ready",
        "user": user_for_client
    }
    if validator_token:
        ready_payload["validator"] = validator_token

    await send_to_client(websocket, ready_payload)

    # Get the color of the first role for user_connect broadcast
    user_roles = user.get("roles", [])
    color = None
    if user_roles:
        first_role_name = user_roles[0]
        first_role_data = roles.get_role(first_role_name)
        if first_role_data:
            color = first_role_data.get("color")

    # Broadcast user connection to all clients (send username, not ID)
    if is_new_user:
        await broadcast_to_all(connected_clients, {
            "cmd": "user_join",
            "user": {
                "username": username,
                "roles": user.get("roles"),
                "color": color
            }
        })
        Logger.success(f"Broadcast user_join: {username} joined the server")

    # Plugin event
    if server_data and "plugin_manager" in server_data:
        server_data["plugin_manager"].trigger_event("user_join", websocket, {
            "username": username,
            "user_id": user_id,
            "roles": user.get("roles"),
            "color": color,
            "user": user
        }, server_data)

    was_online = False
    if server_data and "connected_usernames" in server_data:
        connected_usernames = server_data["connected_usernames"]
        was_online = username in connected_usernames and connected_usernames[username] > 0
        if username not in connected_usernames:
            connected_usernames[username] = 0
        connected_usernames[username] += 1

    if not was_online:
        await broadcast_to_all(connected_clients, {
            "cmd": "user_connect",
            "user": {
                "username": username,
                "roles": user.get("roles"),
                "color": color
            }
        })

    if server_data and "plugin_manager" in server_data:
        server_data["plugin_manager"].trigger_event("user_connect", websocket, {
            "username": username,
            "user_id": user_id,
            "roles": user.get("roles"),
            "color": color,
            "user": user
        }, server_data)

    Logger.success(f"Client {client_ip} authenticated as {username} (ID: {user_id})")
    return True
