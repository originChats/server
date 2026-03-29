from db import channels, users
from handlers.messages.helpers import _error, _require_user_id, _require_user_roles
from handlers.websocket_utils import broadcast_to_all, _get_ws_attr
from logger import Logger
from pydantic import ValidationError
from schemas.slash_command_schema import SlashCommand
from handlers.helpers.validation import validate_embeds
import time
import uuid
import asyncio


async def handle_slash_register(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    user_roles, error = _require_user_roles(user_id)
    if error:
        return error

    commands = message.get("commands")
    if not commands or not isinstance(commands, list):
        return _error("Commands must be provided as a list", match_cmd)

    if not server_data:
        return _error("No server data provided", match_cmd)

    slash_commands = server_data["slash_commands"]
    connected_clients = server_data.get("connected_clients")

    username = users.get_username_by_id(user_id)

    _ws_data_all = server_data.get("_ws_data", {})
    for client_ws in connected_clients:
        if client_ws != ws:
            client_ws_data = _ws_data_all.get(id(client_ws), {})
            client_user_id = client_ws_data.get("user_id")
            if client_user_id == user_id:
                return _error("You already have slash commands registered from another session", match_cmd)

    slash_commands[id(ws)] = {}

    registered_commands = []
    for cmd in commands:
        try:
            validatedCommand = SlashCommand.model_validate(cmd)
        except ValidationError as e:
            return _error(f"Invalid command schema: {str(e)}", match_cmd)

        command_data = {
            "command": validatedCommand,
            "user_id": user_id,
            "username": username
        }
        slash_commands[id(ws)][validatedCommand.name] = command_data
        Logger.info(f"Registered slash command for user {username} ({user_id}): {validatedCommand.name}")
        registered_commands.append({
            "name": validatedCommand.name,
            "description": validatedCommand.description,
            "options": [opt.model_dump() for opt in validatedCommand.options],
            "whitelistRoles": validatedCommand.whitelistRoles,
            "blacklistRoles": validatedCommand.blacklistRoles,
            "ephemeral": validatedCommand.ephemeral,
            "registeredBy": username
        })

    if connected_clients and registered_commands:
        await broadcast_to_all(connected_clients, {
            "cmd": "slash_add",
            "commands": registered_commands
        })

    return {"cmd": "slash_register", "val": f"{len(commands)} commands registered successfully"}


def handle_slash_list(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    user_roles, error = _require_user_roles(user_id)
    if error:
        return error

    if not server_data:
        return _error("No server data provided", match_cmd)

    slash_commands = server_data["slash_commands"]
    commands_list = []

    for key, value in slash_commands.items():
        for cmd_name, cmd_data in value.items():
            command_obj = cmd_data["command"]
            commands_list.append({
                "name": command_obj.name,
                "description": command_obj.description,
                "options": [opt.model_dump() if hasattr(opt, "model_dump") else opt for opt in getattr(command_obj, "options", [])],
                "whitelistRoles": getattr(command_obj, "whitelistRoles", None),
                "blacklistRoles": getattr(command_obj, "blacklistRoles", None),
                "ephemeral": getattr(command_obj, "ephemeral", False),
                "registeredBy": cmd_data.get("username", "originChats")
            })

    return {"cmd": "slash_list", "commands": commands_list}


async def handle_slash_call(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    user_roles, error = _require_user_roles(user_id)
    if error:
        return error

    if not server_data:
        return _error("No server data provided", match_cmd)

    channel = message.get("channel")
    if not channel:
        return _error("Channel parameter is required for slash commands", match_cmd)

    cmd_name = message.get("command")
    args = message.get("args", {})
    if not isinstance(args, dict):
        return {"cmd": "error", "val": "Command args must be an object"}

    if not isinstance(cmd_name, str):
        return _error("Command name must be a string", match_cmd)

    import slash_handlers

    if slash_handlers.handler_exists(cmd_name):
        cmd_roles = slash_handlers.get_command_roles(cmd_name)
        whitelist = cmd_roles.get("whitelist")
        blacklist = cmd_roles.get("blacklist")

        if blacklist and user_roles:
            if any(role in blacklist for role in user_roles):
                return _error("Access denied: forbidden roles", match_cmd)

        if whitelist:
            if not user_roles or not any(role in whitelist for role in user_roles):
                return _error(f"Access denied: '{whitelist[0]}' role required", match_cmd)

        handler = slash_handlers.get_handler(cmd_name)
        is_async = slash_handlers.is_async_handler(cmd_name)
        if handler:
            try:
                invoker_username = users.get_username_by_id(user_id)
                if is_async:
                    result = await handler(ws, args, channel, server_data)
                else:
                    result = handler(ws, args, channel, server_data)

                if "error" in result:
                    return _error(result["error"], match_cmd)

                response_text = result.get("response", "")

                out_msg = {
                    "user": "originChats",
                    "content": response_text,
                    "timestamp": time.time(),
                    "id": str(uuid.uuid4()),
                    "interaction": {
                        "command": cmd_name,
                        "username": invoker_username
                    }
                }

                channels.save_channel_message(channel, out_msg)
                out_msg_for_client = channels.convert_messages_to_user_format([out_msg])
                out_msg_for_client = out_msg_for_client[0]
                out_msg_for_client["interaction"] = out_msg["interaction"]

                return {"cmd": "message_new", "message": out_msg_for_client, "channel": channel, "global": True}

            except Exception as e:
                Logger.error(f"Error executing server slash command /{cmd_name}: {str(e)}")
                return _error(f"Error executing command: {str(e)}", match_cmd)

    slash_commands = server_data["slash_commands"]
    command_data = None
    for user_commands in slash_commands.values():
        if cmd_name in user_commands:
            command_data = user_commands[cmd_name]
            break

    if not command_data:
        return _error(f"Unknown slash command: /{cmd_name}", match_cmd)

    command = command_data["command"]

    def _validate_type(value, expected_type):
        if expected_type == "string":
            if not isinstance(value, str):
                return False, f"Expected string, got {type(value).__name__}"
        elif expected_type == "integer":
            if not isinstance(value, int):
                return False, f"Expected integer, got {type(value).__name__}"
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                return False, f"Expected boolean, got {type(value).__name__}"
        elif expected_type == "number":
            if not isinstance(value, (int, float)):
                return False, f"Expected number, got {type(value).__name__}"
        return True, None

    def _validate_option_value(option_name, value, option):
        expected_type = option.type
        is_valid, error_message = _validate_type(value, expected_type)
        if not is_valid:
            return False, f"Invalid value for '{option_name}': {error_message}"
        return True, None

    user_roles, error = _require_user_roles(user_id, requiredRoles=command.whitelistRoles or [], forbiddenRoles=command.blacklistRoles or [])
    if error:
        return error

    options = {option.name: option for option in command.options}

    for argument_name in args:
        if argument_name not in options:
            return _error(f"Unknown argument: {argument_name}", match_cmd)

    for option in command.options:
        if option.required and option.name not in args:
            return _error(f"Missing required argument: {option.name}", match_cmd)

    for optionName, value in args.items():
        option = options[optionName]

        is_valid, error_message = _validate_option_value(optionName, value, option)
        if not is_valid:
            return {"cmd": "error", "val": error_message}

    commander_user_id = command_data["user_id"]
    invoker_username = users.get_username_by_id(user_id)

    connected_clients = server_data.get("connected_clients", [])
    commander_ws = None

    for client_ws in connected_clients:
        if _get_ws_attr(client_ws, "user_id") == commander_user_id:
            commander_ws = client_ws
            break

    if not commander_ws:
        return _error(f"Command handler for /{cmd_name} is not currently connected", match_cmd)

    slash_call_message = {
        "cmd": "slash_call",
        "val": {"command": cmd_name, "args": args, "commander": command_data["username"]},
        "invoker": user_id,
        "invokerUsername": invoker_username,
        "channel": channel
    }

    Logger.info(f"Sending slash_call to commander {commander_user_id} (username: {command_data['username']}) for command /{cmd_name}")

    loop = asyncio.get_event_loop()
    send_to_client_func = server_data.get("send_to_client")
    if send_to_client_func:
        loop.create_task(send_to_client_func(commander_ws, slash_call_message))

    return slash_call_message


def handle_slash_response(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    user_roles, error = _require_user_roles(user_id)
    if error:
        return error

    channel = message.get("channel")
    if not channel:
        return {"cmd": "error", "val": "Channel parameter is required for slash commands"}

    response = message.get("response")
    embeds = message.get("embeds")

    if not response and not embeds:
        return {"cmd": "error", "val": "Slash response must have content or embeds"}

    if response and not isinstance(response, str):
        return {"cmd": "error", "val": "Slash response must be a string"}

    if response:
        response = response.strip()

    if embeds:
        is_valid, error_msg = validate_embeds(embeds)
        if not is_valid:
            return {"cmd": "error", "val": error_msg}

    command = message.get("command")
    if not command or not isinstance(command, str):
        return {"cmd": "error", "val": "Command parameter is required for slash responses"}

    invoker_id = message.get("invoker") or user_id
    invoker_username = users.get_username_by_id(invoker_id)

    out_msg = {
        "user": user_id,
        "content": response or "",
        "timestamp": time.time(),
        "id": str(uuid.uuid4()),
        "interaction": {
            "command": command,
            "username": invoker_username
        }
    }

    if embeds:
        out_msg["embeds"] = embeds

    channels.save_channel_message(channel, out_msg)
    out_msg_for_client = channels.convert_messages_to_user_format([out_msg])
    out_msg_for_client = out_msg_for_client[0]
    out_msg_for_client["interaction"] = out_msg["interaction"]
    if embeds:
        out_msg_for_client["embeds"] = embeds

    return {"cmd": "message_new", "message": out_msg_for_client, "channel": channel, "global": True}
