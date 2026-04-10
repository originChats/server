import base64
import copy
import hashlib
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
from io import BytesIO
from PIL import Image

from logger import Logger
from config_store import get_config_value
from constants import (
    DEFAULT_MAX_ATTACHMENT_SIZE,
    FILE_SIZE_SMALL_MB, FILE_SIZE_MEDIUM_MB, FILE_SIZE_LARGE_MB,
    EXPIRATION_DAYS_SMALL, IMAGE_MAX_WIDTH, IMAGE_MAX_HEIGHT,
    JPEG_QUALITY, WEBP_QUALITY, PNG_COMPRESSION,
    UNREFERENCED_ATTACHMENT_HOURS,
)

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
attachments_dir = os.path.join(_MODULE_DIR, "attachments")
attachments_index = os.path.join(_MODULE_DIR, "attachments.json")

_attachments_cache: Dict[str, Dict[str, Any]] = {}
_cache_loaded: bool = False
_hash_index: Dict[str, str] = {}  # hash -> attachment_id
_lock = threading.RLock()


def _ensure_storage():
    os.makedirs(attachments_dir, exist_ok=True)
    if not os.path.exists(attachments_index):
        tmp = attachments_index + ".tmp"
        with open(tmp, "w") as f:
            json.dump({}, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, attachments_index)


def _build_hash_index(attachments: Dict[str, Dict[str, Any]]) -> None:
    global _hash_index
    _hash_index = {}
    for att_id, att in attachments.items():
        if "hash" in att:
            _hash_index[att["hash"]] = att_id


def _load_attachments() -> Dict[str, Dict[str, Any]]:
    global _attachments_cache, _cache_loaded, _hash_index
    with _lock:
        _ensure_storage()
        if _cache_loaded:
            return copy.deepcopy(_attachments_cache)
        try:
            with open(attachments_index, "r") as f:
                _attachments_cache = json.load(f)
                if not isinstance(_attachments_cache, dict):
                    _attachments_cache = {}
        except (FileNotFoundError, json.JSONDecodeError):
            _attachments_cache = {}
        _build_hash_index(_attachments_cache)
        _cache_loaded = True
        return copy.deepcopy(_attachments_cache)


def _save_attachments(attachments: Dict[str, Dict[str, Any]]) -> None:
    global _attachments_cache, _cache_loaded
    with _lock:
        tmp = attachments_index + ".tmp"
        with open(tmp, "w") as f:
            json.dump(attachments, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, attachments_index)
        _attachments_cache = copy.deepcopy(attachments)
        _cache_loaded = True


def _generate_attachment_id() -> str:
    return str(uuid.uuid4())


def _get_extension_from_mime(mime_type: str) -> str:
    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/ogg": "ogg",
        "application/pdf": "pdf",
    }
    return mime_to_ext.get(mime_type, "bin")


def get_max_size() -> int:
    return get_config_value("attachments", "max_size", default=DEFAULT_MAX_ATTACHMENT_SIZE)


def calculate_expiration_days(size_bytes: int) -> float:
    mb = size_bytes / (1024 * 1024)
    
    if mb <= FILE_SIZE_SMALL_MB:
        return EXPIRATION_DAYS_SMALL
    elif mb >= FILE_SIZE_LARGE_MB:
        return 1
    elif mb <= FILE_SIZE_MEDIUM_MB:
        return 7 + (FILE_SIZE_MEDIUM_MB - mb) * (42 / 20)
    else:
        return 7 - (mb - FILE_SIZE_MEDIUM_MB) * (6 / 75)


def get_permanent_expiration_days() -> int:
    return get_config_value("attachments", "permanent_expiration_days", default=365)


def get_permanent_tiers() -> List[str]:
    tiers = get_config_value("attachments", "permanent_tiers", default=["pro", "max"])
    return [t.lower() for t in tiers]


def get_max_attachments_per_user() -> int:
    return get_config_value("attachments", "max_attachments_per_user", default=-1)


def get_free_tier_max_expiration_days() -> int:
    return get_config_value("attachments", "free_tier_max_expiration_days", default=7)


def get_user_attachment_count(uploader_id: str) -> int:
    attachments = _load_attachments()
    count = 0
    for att in attachments.values():
        if att.get("uploader_id") == uploader_id and not is_attachment_expired(att):
            count += 1
    return count


def get_oldest_user_attachment(uploader_id: str) -> Optional[Dict[str, Any]]:
    attachments = _load_attachments()
    oldest = None
    oldest_time = float('inf')
    for att in attachments.values():
        if att.get("uploader_id") == uploader_id and not is_attachment_expired(att):
            created_at = att.get("created_at", 0)
            if created_at < oldest_time:
                oldest_time = created_at
                oldest = att
    return oldest


def get_allowed_types() -> List[str]:
    return get_config_value("attachments", "allowed_types", default=["image/*", "video/*", "audio/*", "application/pdf"])


def is_type_allowed(mime_type: str) -> bool:
    allowed = get_allowed_types()
    if not allowed:
        return True
    for pattern in allowed:
        if pattern == "*":
            return True
        if pattern == mime_type:
            return True
        if pattern.endswith("/*"):
            base = pattern[:-1]
            if mime_type.startswith(base):
                return True
    return False


def _save_image_with_compression(image, filepath, mime_type, compression_config):
    width, height = image.width, image.height
    
    if not compression_config.get("enabled", True):
        for key in list(image.info.keys()):
            if isinstance(key, str) and key.lower() in ["exif", "gps", "location", "geotag"]:
                del image.info[key]
        save_kwargs = {"quality": 95} if image.format == "JPEG" else {}
        image.save(filepath, **save_kwargs)
        return width, height

    max_width = compression_config.get("max_width", IMAGE_MAX_WIDTH)
    max_height = compression_config.get("max_height", IMAGE_MAX_HEIGHT)

    if image.width > max_width or image.height > max_height:
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        width, height = image.width, image.height

    if image.mode in ("RGBA", "P") and (image.format == "JPEG" or mime_type == "image/jpeg"):
        if image.mode == "P":
            image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = background

    save_kwargs = {}
    output_format = image.format

    if mime_type == "image/jpeg" or output_format == "JPEG":
        save_kwargs["quality"] = compression_config.get("jpeg_quality", JPEG_QUALITY)
        save_kwargs["optimize"] = True
        if image.mode != "RGB":
            image = image.convert("RGB")
    elif mime_type == "image/webp" or output_format == "WEBP":
        save_kwargs["quality"] = compression_config.get("webp_quality", WEBP_QUALITY)
    elif mime_type == "image/png" or output_format == "PNG":
        save_kwargs["compress_level"] = compression_config.get("png_compression", PNG_COMPRESSION)

    image.save(filepath, **save_kwargs)
    return width, height


def _save_file_bytes(file_bytes, filepath, mime_type, compression_config=None):
    if not (mime_type.startswith("image/") and mime_type != "image/svg+xml"):
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        return None, None

    try:
        image = Image.open(BytesIO(file_bytes))
        width, height = _save_image_with_compression(image, filepath, mime_type, compression_config or {})
        return width, height
    except Exception:
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        return None, None


def save_attachment(
    file_data: str,
    original_name: str,
    mime_type: str,
    uploader_id: str,
    uploader_name: str,
    channel: str,
    permanent: bool = False,
    custom_expires_in_days: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    with _lock:
        _ensure_storage()

        if not is_type_allowed(mime_type):
            Logger.warning(f"Attachment rejected: mime type {mime_type} not allowed")
            return None
        
        Logger.info(f"Processing attachment upload for {uploader_name}: mime={mime_type}, channel={channel}")

        try:
            if file_data.startswith("data:"):
                header, b64_content = file_data.split(",", 1)
                file_bytes = base64.b64decode(b64_content)
            else:
                file_bytes = base64.b64decode(file_data)
        except Exception as e:
            Logger.error(f"Failed to decode attachment data: {e}")
            return None

        size = len(file_bytes)
        max_size = get_max_size()
        if size > max_size:
            Logger.warning(f"Attachment rejected: size {size} exceeds limit {max_size}")
            return None

        max_attachments = get_max_attachments_per_user()
        Logger.info(f"Max attachments per user: {max_attachments}, current count for {uploader_name}: {get_user_attachment_count(uploader_id) if max_attachments > 0 else 'N/A'}")
        
        if max_attachments == 0:
            Logger.warning(f"Attachment rejected: uploads are disabled (max_attachments_per_user=0)")
            return None

        attachments = _load_attachments()
        Logger.info(f"Loaded attachments database, total attachments: {len(attachments)}")

        if max_attachments > 0:
            current_count = get_user_attachment_count(uploader_id)
            Logger.info(f"Checking attachment limit: {current_count}/{max_attachments} for {uploader_name}")
            if current_count >= max_attachments:
                oldest = get_oldest_user_attachment(uploader_id)
                if oldest:
                    Logger.info(f"User {uploader_name} at attachment limit, deleting oldest: {oldest['id']}")
                    delete_attachment_internal(oldest["id"], attachments)

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        Logger.info(f"Generated file hash: {file_hash[:16]}... for {original_name}")

        if file_hash in _hash_index:
            existing_id = _hash_index[file_hash]
            existing_attachment = attachments.get(existing_id)
            if existing_attachment:
                now = time.time()
                if permanent:
                    expiration_days: int | float = get_permanent_expiration_days()
                    if custom_expires_in_days is not None and custom_expires_in_days < expiration_days:
                        expiration_days = custom_expires_in_days
                else:
                    max_expiration_days: int | float = calculate_expiration_days(size)
                    free_tier_max: int = get_free_tier_max_expiration_days()
                    if max_expiration_days > free_tier_max:
                        max_expiration_days = free_tier_max
                    if custom_expires_in_days is not None:
                        expiration_days = min(custom_expires_in_days, max_expiration_days)
                    else:
                        expiration_days = max_expiration_days
                expires_at = now + (expiration_days * 24 * 60 * 60)

                existing_attachment["expires_at"] = expires_at
                existing_attachment["permanent"] = permanent
                existing_attachment["original_name"] = original_name
                _save_attachments(attachments)

                Logger.info(f"Duplicate attachment re-uploaded, expiry reset: {existing_id}")
                return copy.deepcopy(existing_attachment)

        attachment_id = _generate_attachment_id()
        extension = _get_extension_from_mime(mime_type)
        filename = f"{attachment_id}.{extension}"
        filepath = os.path.join(attachments_dir, filename)

        compression_config: Dict[str, Any] = get_config_value("attachments", "compression", default={})
        Logger.info(f"Attempting to save attachment file: {filepath}, compression enabled: {compression_config.get('enabled', True)}")
        width, height = None, None
        try:
            width, height = _save_file_bytes(file_bytes, filepath, mime_type, compression_config)
            Logger.success(f"Attachment file saved successfully: {filepath}")
        except Exception as e:
            Logger.error(f"Failed to save attachment file: {e}")
            import traceback
            Logger.error(traceback.format_exc())
            return None

        actual_size = os.path.getsize(filepath)
    Logger.info(f"File saved, actual size: {actual_size} bytes")

    now = time.time()
    if permanent:
        expiration_days: int | float = get_permanent_expiration_days()
        if custom_expires_in_days is not None and custom_expires_in_days < expiration_days:
            expiration_days = custom_expires_in_days
        expires_at = now + (expiration_days * 24 * 60 * 60)
    else:
        max_expiration_days: int | float = calculate_expiration_days(actual_size)
        free_tier_max: int = get_free_tier_max_expiration_days()
        if max_expiration_days > free_tier_max:
            max_expiration_days = free_tier_max
        if custom_expires_in_days is not None:
            expiration_days = min(custom_expires_in_days, max_expiration_days)
        else:
            expiration_days = max_expiration_days
        expires_at = now + (expiration_days * 24 * 60 * 60)

    attachment = {
        "id": attachment_id,
        "filename": filename,
        "original_name": original_name,
        "mime_type": mime_type,
        "size": actual_size,
        "hash": file_hash,
        "uploader_id": uploader_id,
        "uploader_name": uploader_name,
        "channel": channel,
        "created_at": now,
        "expires_at": expires_at,
        "permanent": permanent,
        "referenced": False,
    }
    if width is not None and height is not None:
        attachment["width"] = width
        attachment["height"] = height

    attachments[attachment_id] = attachment
    _hash_index[file_hash] = attachment_id
    Logger.info(f"Saving attachment metadata to database: {attachment_id}")
    try:
        _save_attachments(attachments)
        Logger.success(f"Attachment metadata saved to database: {attachment_id}")
    except Exception as e:
        Logger.error(f"Failed to save attachment metadata: {e}")
        import traceback
        Logger.error(traceback.format_exc())
        return None

    Logger.success(f"Attachment saved: {attachment_id} by {uploader_name}")
    return attachment


def get_attachment(attachment_id: str) -> Optional[Dict[str, Any]]:
    attachments = _load_attachments()
    attachment = attachments.get(attachment_id)
    if not attachment:
        return None
    if is_attachment_expired(attachment):
        return None
    return copy.deepcopy(attachment)


def get_attachment_file_path(attachment_id: str) -> Optional[str]:
    attachment = get_attachment(attachment_id)
    if not attachment:
        return None
    filepath = os.path.join(attachments_dir, attachment["filename"])
    if os.path.isfile(filepath):
        return filepath
    return None


def delete_attachment_internal(attachment_id: str, attachments: Dict[str, Dict[str, Any]]) -> bool:
    if attachment_id not in attachments:
        return False

    attachment = attachments[attachment_id]
    filepath = os.path.join(attachments_dir, attachment.get("filename", ""))
    file_hash = attachment.get("hash")

    del attachments[attachment_id]
    if file_hash and file_hash in _hash_index:
        del _hash_index[file_hash]

    if filepath and os.path.isfile(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass

    return True


def delete_attachment(attachment_id: str) -> bool:
    with _lock:
        attachments = _load_attachments()
        if attachment_id not in attachments:
            return False

        deleted = delete_attachment_internal(attachment_id, attachments)
        if deleted:
            _save_attachments(attachments)
            Logger.info(f"Attachment deleted: {attachment_id}")
        return deleted


def is_attachment_expired(attachment: Dict[str, Any]) -> bool:
    expires_at = attachment.get("expires_at")
    if expires_at is None:
        return False
    return time.time() > expires_at


def cleanup_expired_attachments() -> int:
    with _lock:
        attachments = _load_attachments()
        expired_ids = []

        for attachment_id, attachment in attachments.items():
            if is_attachment_expired(attachment):
                expired_ids.append(attachment_id)

        for attachment_id in expired_ids:
            attachment = attachments.get(attachment_id)
            if attachment is None:
                continue
            filepath = os.path.join(attachments_dir, attachment.get("filename", ""))
            if filepath and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            del attachments[attachment_id]

        if expired_ids:
            _save_attachments(attachments)
            Logger.info(f"Cleaned up {len(expired_ids)} expired attachments")

        return len(expired_ids)


def get_user_attachments(uploader_id: str) -> List[Dict[str, Any]]:
    attachments = _load_attachments()
    user_attachments = []
    for attachment in attachments.values():
        if attachment.get("uploader_id") == uploader_id:
            if not is_attachment_expired(attachment):
                user_attachments.append(copy.deepcopy(attachment))
    return user_attachments


def get_attachment_info_for_client(attachment: Dict[str, Any], base_url: str = "") -> Dict[str, Any]:
    info = {
        "id": attachment["id"],
        "name": attachment.get("original_name", "file"),
        "mime_type": attachment["mime_type"],
        "size": attachment["size"],
        "url": f"{base_url}/attachments/{attachment['id']}",
        "expires_at": attachment.get("expires_at"),
        "permanent": attachment.get("permanent", False),
    }
    if "width" in attachment:
        info["width"] = attachment["width"]
    if "height" in attachment:
        info["height"] = attachment["height"]
    return info


def mark_attachment_referenced(attachment_id: str) -> bool:
    with _lock:
        attachments = _load_attachments()
        if attachment_id not in attachments:
            return False
        attachments[attachment_id]["referenced"] = True
        _save_attachments(attachments)
        return True


def mark_attachments_referenced(attachment_ids: List[str]) -> int:
    count = 0
    with _lock:
        attachments = _load_attachments()
        for att_id in attachment_ids:
            if att_id in attachments:
                attachments[att_id]["referenced"] = True
                count += 1
        if count > 0:
            _save_attachments(attachments)
    return count


def cleanup_unreferenced_attachments() -> int:
    with _lock:
        attachments = _load_attachments()
        now = time.time()
        one_hour = 3600
        removed_ids = []

        for attachment_id, attachment in attachments.items():
            if attachment.get("referenced", False):
                continue
            created_at = attachment.get("created_at", 0)
            if now - created_at > UNREFERENCED_ATTACHMENT_HOURS * 3600:
                removed_ids.append(attachment_id)

        for attachment_id in removed_ids:
            attachment = attachments.get(attachment_id)
            if attachment is None:
                continue
            filepath = os.path.join(attachments_dir, attachment.get("filename", ""))
            if filepath and os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            del attachments[attachment_id]

        if removed_ids:
            _save_attachments(attachments)
            Logger.info(f"Cleaned up {len(removed_ids)} unreferenced attachments")

        return len(removed_ids)


def run_daily_cleanup() -> dict:
    expired_count = cleanup_expired_attachments()
    unreferenced_count = cleanup_unreferenced_attachments()
    
    total = expired_count + unreferenced_count
    if total > 0:
        Logger.success(f"Daily cleanup complete: {expired_count} expired, {unreferenced_count} unreferenced")
    
    return {
        "expired": expired_count,
        "unreferenced": unreferenced_count,
        "total": total,
    }
