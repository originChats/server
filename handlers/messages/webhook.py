from db import channels, webhooks as webhooks_db
from handlers.messages.helpers import _error, _require_user_id, _require_permission
import copy
import uuid


async def handle_webhook_create(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if not user_id or error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    channel = message.get("channel")
    name = message.get("name")

    if not channel:
        return _error("Channel is required", match_cmd)
    if not name:
        return _error("Webhook name is required", match_cmd)

    if not channels.channel_exists(channel):
        return _error("Channel not found", match_cmd)

    channel_info = channels.get_channel(channel)
    if not channel_info or channel_info.get("type") != "text":
        return _error("Webhooks can only be created for text channels", match_cmd)

    webhook = webhooks_db.create_webhook(channel, name, user_id)
    if not webhook:
        return _error("Failed to create webhook", match_cmd)

    display_webhook = copy.deepcopy(webhook)

    return {"cmd": "webhook_create", "webhook": display_webhook}


async def handle_webhook_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    webhook_id = message.get("id")
    if not webhook_id:
        return _error("Webhook ID is required", match_cmd)

    webhook = webhooks_db.get_webhook(webhook_id)
    if not webhook:
        return _error("Webhook not found", match_cmd)

    if "token" in webhook:
        del webhook["token"]

    return {"cmd": "webhook_get", "webhook": webhook}


async def handle_webhook_list(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    channel = message.get("channel")

    if channel:
        if not channels.channel_exists(channel):
            return _error("Channel not found", match_cmd)
        webhooks_list = webhooks_db.get_webhooks_for_channel(channel)
    else:
        webhooks_list = webhooks_db.get_all_webhooks()

    return {"cmd": "webhook_list", "webhooks": webhooks_list}


async def handle_webhook_delete(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    webhook_id = message.get("id")
    if not webhook_id:
        return _error("Webhook ID is required", match_cmd)

    webhook = webhooks_db.get_webhook(webhook_id)
    if not webhook:
        return _error("Webhook not found", match_cmd)

    deleted = webhooks_db.delete_webhook(webhook_id)
    if not deleted:
        return _error("Failed to delete webhook", match_cmd)

    return {"cmd": "webhook_delete", "id": webhook_id, "deleted": True}


async def handle_webhook_update(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    webhook_id = message.get("id")
    if not webhook_id:
        return _error("Webhook ID is required", match_cmd)

    webhook = webhooks_db.get_webhook(webhook_id)
    if not webhook:
        return _error("Webhook not found", match_cmd)

    updates = {}
    if "name" in message:
        name = message["name"]
        if not name or not isinstance(name, str):
            return _error("Webhook name must be a non-empty string", match_cmd)
        updates["name"] = name.strip()
    if "avatar" in message:
        updates["avatar"] = message["avatar"]

    if not updates:
        return _error("No updates provided", match_cmd)

    updated_webhook = webhooks_db.update_webhook(webhook_id, updates)
    if not updated_webhook:
        return _error("Failed to update webhook", match_cmd)

    return {"cmd": "webhook_update", "webhook": updated_webhook}


async def handle_webhook_regenerate(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    webhook_id = message.get("id")
    if not webhook_id:
        return _error("Webhook ID is required", match_cmd)

    webhook = webhooks_db.get_webhook(webhook_id)
    if not webhook:
        return _error("Webhook not found", match_cmd)

    new_token = str(uuid.uuid4()) + str(uuid.uuid4()).replace("-", "")

    updated_webhook = webhooks_db.update_webhook(webhook_id, {"token": new_token})
    if not updated_webhook:
        return _error("Failed to regenerate webhook token", match_cmd)

    webhook_with_token = webhooks_db.get_webhook(webhook_id)

    return {"cmd": "webhook_regenerate", "webhook": webhook_with_token}
