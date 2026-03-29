from typing import List, Optional, Tuple

from . import roles
from . import users
from . import channels


PERMISSIONS = {
    # Server Management
    "administrator": "Full permissions (bypasses all checks except owner)",
    "manage_server": "Update server settings, emojis, and webhooks",
    "view_audit_log": "View server audit logs",

    # Role Management
    "manage_roles": "Create, delete, and assign roles below own position",

    # Channel Management
    "manage_channels": "Create, delete, and configure channels",
    "manage_threads": "Lock, archive, and delete threads",

    # User Moderation
    "manage_users": "Ban, unban, timeout, and manage user nicknames",
    "kick_members": "Kick users from the server",
    "manage_nicknames": "Change other users' nicknames",
    "change_nickname": "Change own nickname",

    # Voice Channel
    "connect": "Connect to voice channels",
    "speak": "Speak in voice channels",
    "stream": "Stream video in voice channels",
    "mute_members": "Mute users in voice channels",
    "deafen_members": "Deafen users in voice channels",
    "move_members": "Move users between voice channels",
    "use_voice_activity": "Use voice activity detection (vs push-to-talk)",
    "priority_speaker": "Be heard over other speakers in voice channels",

    # Message Management
    "manage_messages": "Delete and pin any message across all channels",
    "read_message_history": "View previous messages in channel",

    # Messaging
    "send_messages": "Send messages in text channels",
    "send_tts": "Send text-to-speech messages",
    "embed_links": "Embed links in messages",
    "attach_files": "Attach files to messages",
    "add_reactions": "Add reactions to messages",
    "external_emojis": "Use external/custom emojis",

    # Invites
    "create_invite": "Create channel invites",
    "manage_invites": "Manage and revoke invites",

    # Special
    "mention_everyone": "Mention the @everyone role",
    "use_slash_commands": "Use slash commands in chat",
}


def get_all_permissions() -> dict:
    return PERMISSIONS.copy()


def get_user_roles_sorted(user_id: str) -> List[str]:
    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return []

    role_positions = {}
    for role_name in user_roles:
        role_data = roles.get_role(role_name)
        if role_data:
            role_positions[role_name] = role_data.get("position", 0)
        else:
            role_positions[role_name] = 9999

    return sorted(user_roles, key=lambda r: role_positions.get(r, 9999))


def get_highest_role_position(user_id: str) -> int:
    user_roles = get_user_roles_sorted(user_id)
    if not user_roles:
        return -1

    highest_role_name = user_roles[0]
    role_data = roles.get_role(highest_role_name)
    if role_data:
        return role_data.get("position", 0)
    return 9999


def role_has_permission(role_name: str, permission: str) -> bool:
    if role_name == "owner":
        return True

    role_data = roles.get_role(role_name)
    if not role_data:
        return False

    role_permissions = role_data.get("permissions", [])

    if "administrator" in role_permissions:
        return True

    return permission in role_permissions


def has_permission(user_id: str, permission: str, channel_name: Optional[str] = None) -> bool:
    user_roles = users.get_user_roles(user_id)

    if not user_roles:
        return False

    if "owner" in user_roles:
        return True

    for role_name in user_roles:
        if role_has_permission(role_name, permission):
            if channel_name:
                channel_data = channels.get_channel(channel_name)
                if channel_data:
                    channel_perms = channel_data.get("permissions", {})
                    denied = channel_perms.get("deny", [])
                    if permission in denied:
                        return False
            return True

    return False


def can_manage_role(actor_id: str, target_role: str) -> Tuple[bool, Optional[str]]:
    if not has_permission(actor_id, "manage_roles"):
        return False, "Missing 'manage_roles' permission"

    actor_roles = get_user_roles_sorted(actor_id)
    if not actor_roles:
        return False, "No roles found"

    if "owner" in actor_roles:
        return True, None

    target_role_data = roles.get_role(target_role)
    if not target_role_data:
        return False, f"Role '{target_role}' not found"

    target_position = target_role_data.get("position", 0)
    actor_highest_position = get_highest_role_position(actor_id)

    if target_position <= actor_highest_position:
        return False, "Cannot manage roles at or above your position"

    if target_role_data.get("name") in ["owner", "admin"]:
        return False, f"Cannot manage protected role '{target_role}'"

    return True, None


def can_assign_role_to_user(actor_id: str, target_user_id: str, role_name: str) -> Tuple[bool, Optional[str]]:
    can_manage, error = can_manage_role(actor_id, role_name)
    if not can_manage:
        return False, error

    target_roles = users.get_user_roles(target_user_id)

    if "owner" in target_roles and "owner" not in users.get_user_roles(actor_id):
        return False, "Cannot modify roles of the server owner"

    return True, None


def has_channel_permission(user_id: str, channel_name: str, permission_type: str) -> bool:
    user_roles = users.get_user_roles(user_id)

    if not user_roles:
        return False

    if "owner" in user_roles:
        return True

    for role_name in user_roles:
        if role_name == "owner":
            return True

    return channels.does_user_have_permission(channel_name, user_roles, permission_type)


def require_permission(user_id: str, permission: str, channel_name: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    if has_permission(user_id, permission, channel_name):
        return True, None

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return False, "Authentication required"

    return False, f"Missing permission: {permission}"
