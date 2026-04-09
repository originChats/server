import requests
from db import users, roles, push as push_db
from handlers.websocket_utils import (
    send_to_client,
    broadcast_to_all,
    _get_ws_attr,
    _set_ws_attr,
)
from logger import Logger
from config_store import get_config_value


async def _send_auth_success(
    websocket,
    user_id,
    username,
    user,
    is_new_user,
    connected_clients,
    server_data,
    client_ip,
    is_cracked=False,
):
    _set_ws_attr(websocket, "authenticated", True)
    _set_ws_attr(websocket, "user_id", user_id)
    _set_ws_attr(websocket, "username", username)
    _set_ws_attr(websocket, "user_roles", user.get("roles", []))

    await send_to_client(
        websocket, {"cmd": "auth_success", "val": "Authentication successful"}
    )

    user["username"] = username
    validator_token = users.generate_validator(user_id)
    user_for_client = {
        k: v for k, v in user.items() if k != "validator" and k != "password_hash"
    }
    user_for_client["cracked"] = is_cracked

    ready_payload = {"cmd": "ready", "user": user_for_client}
    if validator_token:
        ready_payload["validator"] = validator_token

    await send_to_client(websocket, ready_payload)

    user_roles = user.get("roles", [])
    color = roles.get_user_color(user_roles)

    if is_new_user:
        await broadcast_to_all(
            connected_clients,
            {
                "cmd": "user_join",
                "user": {
                    "username": username,
                    "roles": user.get("roles"),
                    "color": color,
                },
            },
        )
        Logger.success(f"Broadcast user_join: {username} joined the server")

    if server_data and "plugin_manager" in server_data:
        server_data["plugin_manager"].trigger_event(
            "user_join",
            websocket,
            {
                "username": username,
                "user_id": user_id,
                "roles": user.get("roles"),
                "color": color,
                "user": user,
            },
            server_data,
        )

    connected_usernames = (
        server_data.get("connected_usernames", {}) if server_data else {}
    )
    was_online = (
        username in connected_usernames and connected_usernames.get(username, 0) > 0
    )
    if username not in connected_usernames:
        connected_usernames[username] = 0
    connected_usernames[username] += 1

    if not was_online:
        await broadcast_to_all(
            connected_clients,
            {
                "cmd": "user_connect",
                "user": {
                    "username": username,
                    "roles": user.get("roles"),
                    "color": color,
                },
            },
        )

        if server_data and "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event(
                "user_connect",
                websocket,
                {
                    "username": username,
                    "user_id": user_id,
                    "roles": user.get("roles"),
                    "color": color,
                    "user": user,
                },
                server_data,
            )

    Logger.success(f"Client {client_ip} authenticated as {username} (ID: {user_id})")
    return True


async def handle_cracked_auth(
    websocket, data, _config_data, connected_clients, client_ip, server_data=None
):
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": "Username and password required"}
        )
        return False

    success, user_id, error = users.authenticate_cracked_user(username, password)
    if not success:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": error or "Authentication failed"}
        )
        Logger.error(f"Client {client_ip} failed cracked auth: {error}")
        return False

    user = users.get_user(user_id)
    if not user:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": "User not found"}
        )
        Logger.error(f"Client {client_ip} user not found after auth: {user_id}")
        return False

    if users.is_user_banned(user_id):
        await send_to_client(
            websocket,
            {
                "cmd": "auth_error",
                "val": "Access denied: You are banned from this server",
            },
        )
        Logger.warning(
            f"Banned user {username} (ID: {user_id}) attempted to connect from {client_ip}"
        )
        return False

    stored_username = user.get("username", username)
    return await _send_auth_success(
        websocket,
        user_id,
        stored_username,
        user,
        False,
        connected_clients,
        server_data,
        client_ip,
        is_cracked=True,
    )


async def handle_cracked_register(
    websocket, data, _config_data, connected_clients, client_ip, server_data=None
):
    allow_registration = get_config_value("cracked", "allow_registration", default=True)
    if not allow_registration:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": "Registration is disabled"}
        )
        return False

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": "Username and password required"}
        )
        return False

    default_roles = get_config_value(
        "DB", "users", "default", "roles", default=["user"]
    )
    success, user_id, error = users.register_cracked_user(
        username, password, default_roles
    )

    if not success:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": error or "Registration failed"}
        )
        Logger.error(f"Client {client_ip} failed registration: {error}")
        return False

    user = users.get_user(user_id)
    if not user:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": "User not found after registration"}
        )
        Logger.error(f"Client {client_ip} user not found after registration: {user_id}")
        return False

    stored_username = user.get("username", username)
    Logger.add(f"New cracked user registered: {stored_username} (ID: {user_id})")

    return await _send_auth_success(
        websocket,
        user_id,
        stored_username,
        user,
        True,
        connected_clients,
        server_data,
        client_ip,
        is_cracked=True,
    )


async def handle_authentication(
    websocket,
    data,
    _config_data,
    connected_clients,
    client_ip,
    server_data=None,
    validator_key=None,
):
    url = "https://api.rotur.dev/validate"
    key = validator_key
    validator = data.get("validator")

    response = requests.get(url, params={"key": key, "v": validator}, timeout=5)
    if response.status_code != 200 or response.json().get("valid") != True:
        await send_to_client(
            websocket, {"cmd": "auth_error", "val": "Invalid authentication"}
        )
        Logger.error(f"Client {client_ip} failed authentication")
        return False

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
        await send_to_client(
            websocket,
            {
                "cmd": "auth_error",
                "val": "Access denied: You are banned from this server",
            },
        )
        Logger.warning(
            f"Banned user {username} (ID: {user_id}) attempted to connect from {client_ip}"
        )
        _set_ws_attr(websocket, "authenticated", False)
        return False

    request = _get_ws_attr(websocket, "request")
    if request:
        headers = request.headers
        ip = (
            headers.get("CF-Connecting-IP", "")
            or headers.get("X-Forwarded-For", "").split(",")[0].strip()
        )
        user_agent = headers.get("User-Agent", "")
        country = headers.get("CF-IPCountry", "")
        device_fingerprint = push_db.compute_device_fingerprint(ip, user_agent, country)
        push_db.update_last_used(username, device_fingerprint)

    is_new_user = not users.user_exists(user_id)
    default_roles = get_config_value(
        "DB", "users", "default", "roles", default=["user"]
    )
    if is_new_user:
        added = users.add_user(user_id, username, default_roles=default_roles)
        if added:
            Logger.add(f"User {username} (ID: {user_id}) created")
            _set_ws_attr(websocket, "user_roles", default_roles)
        else:
            is_new_user = False
            Logger.warning(
                f"User {username} (ID: {user_id}) was added by another process"
            )
    elif user:
        _set_ws_attr(websocket, "user_roles", user.get("roles", []))

    existing_user = users.get_user(user_id)
    if existing_user and existing_user.get("username") != username:
        users.update_user_username(user_id, username)
        Logger.add(f"Updated username for ID {user_id} to {username}")

    user = users.get_user(user_id)
    if not user:
        await send_to_client(websocket, {"cmd": "auth_error", "val": "User not found"})
        Logger.error(f"User {username} (ID: {user_id}) not found after authentication")
        return False

    return await _send_auth_success(
        websocket,
        user_id,
        username,
        user,
        is_new_user,
        connected_clients,
        server_data,
        client_ip,
    )
