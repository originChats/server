from typing import Dict, Any, Optional
from pydantic import ValidationError
from schemas.attachment_schema import Attachment_delete, Attachment_get
from db import attachments as attachments_db
from handlers.messages.helpers import _error, _require_user_id
from handlers.websocket_utils import _get_ws_attr
from logger import Logger


async def handle_attachment_delete(ws, message: Dict[str, Any], server_data: Dict[str, Any], match_cmd: str) -> Optional[Dict[str, Any]]:
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    try:
        delete_cmd = Attachment_delete.model_validate(message)
    except ValidationError as e:
        return _error(f"Invalid attachment_delete command: {str(e)}", match_cmd)

    attachment = attachments_db.get_attachment(delete_cmd.attachment_id)
    if not attachment:
        return _error("Attachment not found", match_cmd)

    user_roles = _get_ws_attr(ws, "user_roles", [])
    if "owner" not in user_roles and "admin" not in user_roles:
        if attachment.get("uploader_id") != user_id:
            return _error("You can only delete your own attachments", match_cmd)

    deleted = attachments_db.delete_attachment(delete_cmd.attachment_id)
    if not deleted:
        return _error("Failed to delete attachment", match_cmd)

    Logger.info(f"Attachment deleted: {delete_cmd.attachment_id}")

    return {
        "cmd": "attachment_deleted",
        "attachment_id": delete_cmd.attachment_id,
        "deleted": True,
    }


async def handle_attachment_get(ws, message: Dict[str, Any], server_data: Dict[str, Any], match_cmd: str) -> Optional[Dict[str, Any]]:
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    try:
        get_cmd = Attachment_get.model_validate(message)
    except ValidationError as e:
        return _error(f"Invalid attachment_get command: {str(e)}", match_cmd)

    attachment = attachments_db.get_attachment(get_cmd.attachment_id)
    if not attachment:
        return _error("Attachment not found or expired", match_cmd)

    config = server_data.get("config", {})
    base_url = ""
    if "server" in config and "url" in config["server"]:
        base_url = config["server"]["url"].rstrip("/")

    attachment_info = attachments_db.get_attachment_info_for_client(attachment, base_url)

    return {
        "cmd": "attachment_info",
        "attachment": attachment_info,
    }


ATTACHMENT_HANDLERS = {
    "attachment_delete": handle_attachment_delete,
    "attachment_get": handle_attachment_get,
}
