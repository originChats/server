"""Constants used throughout the OriginChats codebase."""

DEFAULT_MAX_ATTACHMENT_SIZE = 100 * 1024 * 1024  # 100MB

HEARTBEAT_INTERVAL = 30  # seconds

ALLOWED_STATUSES = {"online", "idle", "dnd", "offline", "invisible"}

PROTECTED_ROLES = {"owner", "admin", "moderator"}

MAX_NICKNAME_LENGTH = 20

FILE_SIZE_SMALL_MB = 5
FILE_SIZE_MEDIUM_MB = 25
FILE_SIZE_LARGE_MB = 100
EXPIRATION_DAYS_SMALL = 49

IMAGE_MAX_WIDTH = 1920
IMAGE_MAX_HEIGHT = 1920
JPEG_QUALITY = 85
WEBP_QUALITY = 85
PNG_COMPRESSION = 6

UNREFERENCED_ATTACHMENT_HOURS = 1
SIX_MONTHS_SECONDS = 6 * 30 * 24 * 60 * 60

AUDIT_CATEGORIES: dict[str, str] = {
    "user_ban": "user_moderation",
    "user_unban": "user_moderation",
    "user_timeout": "user_moderation",
    "user_roles_set": "user_moderation",
    "user_update": "user_moderation",

    "role_create": "role_management",
    "role_update": "role_management",
    "role_delete": "role_management",
    "role_reorder": "role_management",
    "role_permissions_set": "role_management",
    "self_role_add": "role_management",
    "self_role_remove": "role_management",

    "channel_create": "channel_management",
    "channel_update": "channel_management",
    "channel_move": "channel_management",
    "channel_delete": "channel_management",

    "message_delete": "message_moderation",
    "message_pin": "message_moderation",
    "message_unpin": "message_moderation",

    "server_update": "server_management",
    "emoji_add": "server_management",
    "emoji_update": "server_management",
    "emoji_delete": "server_management",
    "webhook_create": "server_management",
    "webhook_update": "server_management",
    "webhook_delete": "server_management",
    "webhook_regenerate": "server_management",
    "plugins_reload": "server_management",
}

FALLBACK_RETENTION_DAYS = 90
