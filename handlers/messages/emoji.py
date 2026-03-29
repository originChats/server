from db import serverEmojis
from pydantic import ValidationError
from schemas.server_emoji_schema import Emoji_add, Emoji_delete, Emoji_get_all, Emoji_update, Emoji_get_filename, Emoji_get_id
from handlers.messages.helpers import _error, _require_user_id, _require_permission


async def handle_emoji_add(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    try:
        emoji_add_command = Emoji_add.model_validate(message)
        emoji_id = serverEmojis.add_emoji(emoji_add_command.name, emoji_add_command.image)
        if emoji_id:
            return {"cmd": "emoji_add", "id": emoji_id, "added": True}
        else:
            return _error("Error adding emoji", match_cmd)
    except ValidationError as e:
        return _error(f"Invalid emoji_add command scheme: {str(e)}", match_cmd)


def handle_emoji_delete(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    try:
        emoji_delete_command = Emoji_delete.model_validate(message)
        deleted = serverEmojis.remove_emoji(emoji_delete_command.emoji_id, True)
        return {"cmd": "emoji_delete", "id": emoji_delete_command.emoji_id, "deleted": deleted}
    except ValidationError as e:
        return _error(f"Invalid emoji_delete command scheme: {str(e)}", match_cmd)


def handle_emoji_get_all(ws, message, match_cmd):
    _, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    try:
        Emoji_get_all.model_validate(message)
        all_emojis = serverEmojis.get_emojis()
        return {"cmd": "emoji_get_all", "emojis": all_emojis}
    except ValidationError as e:
        return _error(f"Invalid emoji_get_all command scheme: {str(e)}", match_cmd)


async def handle_emoji_update(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    try:
        emoji_update_command = Emoji_update.model_validate(message)
        updates = {}
        if emoji_update_command.name is not None:
            updates["name"] = emoji_update_command.name
        if emoji_update_command.image is not None:
            updates["fileName"] = str(emoji_update_command.image)

        if not updates:
            return _error("At least one field to update is required (name or image)", match_cmd)

        updated = serverEmojis.update_emoji(emoji_update_command.emoji_id, updates)
        return {"cmd": "emoji_update", "id": emoji_update_command.emoji_id, "updated": updated}
    except ValidationError as e:
        return _error(f"Invalid emoji_update command scheme: {str(e)}", match_cmd)


async def handle_emoji_get_filename(ws, message, match_cmd):
    _, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    try:
        emoji_get_filename_command = Emoji_get_filename.model_validate(message)
        emoji_id = serverEmojis.get_emoji_id_by_name(emoji_get_filename_command.name)
        if emoji_id is None:
            return _error("Emoji not found", match_cmd)

        file_path = serverEmojis.get_emoji_file_name(emoji_id)
        if not file_path:
            return _error("Emoji file not found", match_cmd)

        return {"cmd": "emoji_get_filename", "name": emoji_get_filename_command.name, "filepath": file_path}
    except ValidationError as e:
        return _error(f"Invalid emoji_get_filename command scheme: {str(e)}", match_cmd)


async def handle_emoji_get_id(ws, message, match_cmd):
    _, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    try:
        emoji_get_id_command = Emoji_get_id.model_validate(message)
        emoji_id = serverEmojis.get_emoji_id_by_name(emoji_get_id_command.name)
        if emoji_id is None:
            return _error("Emoji not found", match_cmd)
        return {"cmd": "emoji_get_id", "name": emoji_get_id_command.name, "id": emoji_id}
    except ValidationError as e:
        return _error(f"Invalid emoji_get_id command scheme: {str(e)}", match_cmd)


EMOJI_HANDLERS = {
    "emoji_add": handle_emoji_add,
    "emoji_delete": handle_emoji_delete,
    "emoji_get_all": handle_emoji_get_all,
    "emoji_update": handle_emoji_update,
    "emoji_get_filename": handle_emoji_get_filename,
    "emoji_get_id": handle_emoji_get_id,
}
