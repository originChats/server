import json
import os
import re
import base64
import threading
from PIL import Image
from io import BytesIO

from typing import Any, Dict, Optional

import emoji
from logger import Logger

# TODO: move config setup into separate file and add part that allows/disallows file types

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
server_emojis_db = os.path.join(_MODULE_DIR, "serverEmojis")
server_emojis_index = os.path.join(_MODULE_DIR, "serverEmojis.json")

allowed_file_types = ["gif", "jpg", "jpeg"]
name_to_id: Dict[str, str] = {}
_emoji_lock = threading.RLock()

def _ensure_storage() -> None:
    os.makedirs(server_emojis_db, exist_ok=True)
    if not os.path.exists(server_emojis_index):
        with open(server_emojis_index, "w") as f:
            json.dump({}, f, indent=4)

def _write_emojis(emojis: Dict[str, Dict[str, Any]]) -> None:
    with open(server_emojis_index, "w") as f:
        json.dump(emojis, f, indent=4)

def _normalize_name(name: str) -> str:
    return str(name).strip()

def _name_key(name: str) -> str:
    return _normalize_name(name).lower()

def _normalize_extension(file_or_ext: str) -> str:
    file_or_ext = str(file_or_ext).strip().lower()
    if "." in file_or_ext:
        file_or_ext = file_or_ext.rsplit(".", 1)[1]
    return file_or_ext

def is_allowed_file_type(file_or_ext: str) -> bool:
    return _normalize_extension(file_or_ext) in allowed_file_types

def _generate_name_to_id(emojis: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """
    Index all emojis for fast lookup.

    Args:
        emojis: Unpacked emojis.
    """
    global name_to_id
    updated_name_to_id: Dict[str, str] = {}
    for emoji_id, data in emojis.items():
        if not isinstance(data, dict):
            continue
        emoji_name = data.get("name")
        if not emoji_name:
            continue
        updated_name_to_id[_name_key(emoji_name)] = str(emoji_id)
    name_to_id = updated_name_to_id
    return name_to_id

def get_emojis() -> Dict[str, Dict[str, Any]]:
    """
    Get all emojis from the server emojis index.

    Returns:
        A dict of emoji info keyed by emoji ID.
    """
    with _emoji_lock:
        _ensure_storage()
        try:
            with open(server_emojis_index, "r") as f:
                emojis = json.load(f)
                if not isinstance(emojis, dict):
                    emojis = {}
        except (FileNotFoundError, json.JSONDecodeError):
            emojis = {}

        _generate_name_to_id(emojis)
        return emojis

def get_emoji(emoji_id: str) -> Optional[Dict[str, Any]]:
    return get_emojis().get(str(emoji_id))

def emoji_exists(emoji_id: str) -> bool:
    return str(emoji_id) in get_emojis()

def get_emoji_id_by_name(name: str) -> Optional[str]:
    with _emoji_lock:
        if not name_to_id:
            _generate_name_to_id(get_emojis())
        return name_to_id.get(_name_key(name))

def emoji_name_exists(name: str) -> bool:
    return get_emoji_id_by_name(name) is not None

def _next_emoji_id(emojis: Dict[str, Dict[str, Any]]) -> str:
    numeric_ids = [int(k) for k in emojis.keys() if str(k).isdigit()]
    return str((max(numeric_ids) + 1) if numeric_ids else 0)

def get_emoji_file_name(emoji_id: str) -> Optional[str]:
    emoji_data = get_emoji(emoji_id)
    if not emoji_data:
        return None
    file_name = emoji_data.get("fileName")
    if not file_name:
        return None
    return file_name

def _download_emoji(b64_image: str) -> str | None:
    """
    Donwload emoji from Base64 uri.
    
    Args:
        b64_image: base 64 image uri.
        
    Returns:
        Filepath on sucess, None on failure.
    """
    try:
        img_data = base64.b64decode(b64_image.split(',', 1)[-1])
        image = Image.open(BytesIO(img_data))
        extension = image.format.lower() if image.format else 'jpg'
        
        path = os.path.join("db", os.path.join("serverEmojis", f"{_next_emoji_id}.{extension}"))
        image.save(path)
        return path
    except Exception as e:
        Logger.error("Failed to save image: {e}")
        return None
    
def _add_emoji_by_filepath(name: str, file_name: str) -> Optional[str]:
    """
    Add a server emoji metadata entry assuming emoji has been downloaded.

    Args:
        name: name for emoji
        file_name: file path to emoji

    Returns:
        New emoji ID on success, None on failure.
    """
    cleaned_name = _normalize_name(name)
    if not cleaned_name:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", cleaned_name):
        return None
    if not file_name or not is_allowed_file_type(file_name):
        return None

    with _emoji_lock:
        emojis = get_emojis()
        if _name_key(cleaned_name) in name_to_id:
            return None
        emoji_id = _next_emoji_id(emojis)

        entry: Dict[str, Any] = {
            "name": cleaned_name,
            "fileName": file_name
        }

        emojis[emoji_id] = entry
        _write_emojis(emojis)
        _generate_name_to_id(emojis)
        return emoji_id

def add_emoji(name: str, b64_image: str) -> Optional[str]:
    """
    Add a server emoji metadata entry.

    Args:
        name: name for emoji
        b64_image: base 64 image uri.

    Returns:
        New emoji ID on success, None on failure.
    """
    filepath = _download_emoji(b64_image)
    if filepath:
        return _add_emoji_by_filepath(name, filepath)
    else:
        return None
    

def update_emoji(emoji_id: str | int, updates: Dict[str, Any]) -> bool:
    """
    Update mutable emoji fields .
    Supported keys: name, fileName
    """
    emoji_id = str(emoji_id)
    if not isinstance(updates, dict):
        return False

    with _emoji_lock:
        emojis = get_emojis()
        if emoji_id not in emojis:
            return False

        current = emojis[emoji_id]

        if "name" in updates:
            new_name = _normalize_name(updates["name"])
            if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", new_name):
                return False
            existing_id = name_to_id.get(_name_key(new_name))
            if existing_id is not None and existing_id != emoji_id:
                return False
            current["name"] = new_name

        if "fileName" in updates:
            new_file = str(updates["fileName"]).strip()
            if not new_file or not is_allowed_file_type(new_file):
                return False
            current["fileName"] = new_file

        emojis[emoji_id] = current
        _write_emojis(emojis)
        _generate_name_to_id(emojis)
        return True

def remove_emoji(emoji_id: str | int, delete_file: bool = False) -> bool:
    emoji_id = str(emoji_id)
    with _emoji_lock:
        emojis = get_emojis()
        if emoji_id not in emojis:
            return False

        file_name = emojis[emoji_id].get("fileName")
        file_path = os.path.join(server_emojis_db, file_name) if file_name else None
        del emojis[emoji_id]
        _write_emojis(emojis)
        _generate_name_to_id(emojis)

    if delete_file and file_path and os.path.isfile(file_path):
        os.remove(file_path)

    return True

def is_valid_emoji_value(value: str) -> bool:
    """
    Validate if a value is either a unicode emoji or an existing custom emoji name in :name: form.
    """
    if not value:
        return False
    if emoji.is_emoji(value):
        return True

    if value.startswith(":") and value.endswith(":") and len(value) > 2:
        name = value[1:-1]
        return emoji_name_exists(name)

    return False
