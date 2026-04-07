import copy
import json
import os
import threading
import uuid

from constants import PROTECTED_ROLES

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
roles_index = os.path.join(_MODULE_DIR, "roles.json")

DEFAULT_ROLES = {
    "owner": {
        "id": None,
        "description": "Server owner with ultimate permissions.",
        "color": "#9400D3",
        "hoisted": True,
        "permissions": ["administrator"],
        "self_assignable": False,
        "category": None,
        "position": 0
    },
    "admin": {
        "id": None,
        "description": "Administrator role with full permissions.",
        "color": "#FF0000",
        "hoisted": True,
        "permissions": [
            "administrator",
            "manage_roles", "manage_channels", "manage_users", "manage_server",
            "manage_messages", "manage_threads", "manage_nicknames",
            "kick_members", "ban_members",
            "create_invite", "manage_invites",
            "mention_everyone", "use_slash_commands"
        ],
        "self_assignable": False,
        "category": None,
        "position": 1
    },
    "moderator": {
        "id": None,
        "description": "Moderator role with elevated permissions.",
        "color": "#FFFF00",
        "hoisted": True,
        "permissions": [
            "manage_messages", "manage_threads",
            "kick_members", "manage_nicknames",
            "mute_members", "deafen_members", "move_members",
            "create_invite", "use_slash_commands"
        ],
        "self_assignable": False,
        "category": None,
        "position": 2
    },
    "user": {
        "id": None,
        "description": "Regular user role with standard permissions.",
        "color": "#FFFFFF",
        "hoisted": False,
        "permissions": [
            "send_messages", "read_message_history",
            "add_reactions", "attach_files", "embed_links", "external_emojis",
            "connect", "speak", "stream", "use_voice_activity",
            "change_nickname", "create_invite", "use_slash_commands"
        ],
        "self_assignable": False,
        "category": None,
        "position": 3
    }
}

_lock = threading.RLock()
_roles_cache: dict = {}
_roles_loaded: bool = False


def _load_roles() -> dict:
    global _roles_cache, _roles_loaded
    try:
        with open(roles_index, "r") as f:
            _roles_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _roles_cache = copy.deepcopy(DEFAULT_ROLES)
        for role_name in _roles_cache:
            _roles_cache[role_name]["id"] = str(uuid.uuid4())
        _save_roles(_roles_cache)
    _roles_loaded = True
    return _roles_cache


def reload_roles() -> dict:
    global _roles_loaded
    _roles_loaded = False
    return _load_roles()


def get_user_color(user_roles: list) -> str | None:
    if not user_roles:
        return None
    first_role_data = get_role(user_roles[0])
    return first_role_data.get("color") if first_role_data else None


def _save_roles(roles_dict: dict) -> None:
    global _roles_cache, _roles_loaded
    tmp = roles_index + ".tmp"
    with open(tmp, "w") as f:
        json.dump(roles_dict, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, roles_index)
    _roles_cache = roles_dict
    _roles_loaded = True


def _get_roles_cache() -> dict:
    if not _roles_loaded:
        _load_roles()
    return _roles_cache


def _ensure_storage():
    os.makedirs(_MODULE_DIR, exist_ok=True)
    if not os.path.exists(roles_index):
        default = copy.deepcopy(DEFAULT_ROLES)
        for role_name in default:
            default[role_name]["id"] = str(uuid.uuid4())
        tmp = roles_index + ".tmp"
        with open(tmp, "w") as f:
            json.dump(default, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, roles_index)


_ensure_storage()


def get_role(role_id_or_name):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                return copy.deepcopy(role_data)
        return None


def get_role_by_name(role_name):
    with _lock:
        roles = _get_roles_cache()
        if role_name in roles:
            return copy.deepcopy(roles[role_name])
        return None


def get_role_by_id(role_id):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id:
                return copy.deepcopy(role_data)
        return None


def count_roles() -> int:
    with _lock:
        return len(_get_roles_cache())


def get_all_roles():
    with _lock:
        return copy.deepcopy(_get_roles_cache())


def add_role(role_name, role_data):
    with _lock:
        roles = _get_roles_cache()
        if role_name in roles:
            return roles[role_name].get("id")

        role_id = str(uuid.uuid4())
        new_role = {
            "id": role_id,
            "description": role_data.get("description"),
            "color": role_data.get("color"),
            "hoisted": role_data.get("hoisted", False),
            "permissions": role_data.get("permissions", []),
            "self_assignable": role_data.get("self_assignable", False),
            "category": role_data.get("category"),
            "position": role_data.get("position", len(roles))
        }
        roles[role_name] = new_role
        _save_roles(roles)
        return role_id


def update_role(role_id_or_name, role_data):
    with _lock:
        roles = _get_roles_cache()
        for role_name, data in roles.items():
            if data.get("id") == role_id_or_name or role_name == role_id_or_name:
                if "name" in role_data and role_data["name"] != role_name:
                    roles[role_data["name"]] = roles.pop(role_name)
                    role_name = role_data["name"]
                roles[role_name].update({
                    "description": role_data.get("description", roles[role_name].get("description")),
                    "color": role_data.get("color", roles[role_name].get("color")),
                    "hoisted": role_data.get("hoisted", roles[role_name].get("hoisted", False)),
                    "permissions": role_data.get("permissions", roles[role_name].get("permissions", [])),
                    "self_assignable": role_data.get("self_assignable", roles[role_name].get("self_assignable", False)),
                    "category": role_data.get("category", roles[role_name].get("category")),
                    "position": role_data.get("position", roles[role_name].get("position", 0))
                })
                _save_roles(roles)
                return True
        return False


def update_role_key(role_id_or_name, key, value):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                roles[role_name][key] = value
                _save_roles(roles)
                return True
        return False


def delete_role(role_id_or_name):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in list(roles.items()):
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                del roles[role_name]
                _save_roles(roles)
                return True
        return False


def role_exists(role_id_or_name):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                return True
        return False


def add_role_permission(role_id_or_name, permission, value=True):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                permissions = role_data.get("permissions", [])
                if isinstance(permissions, list):
                    if permission not in permissions:
                        permissions.append(permission)
                        roles[role_name]["permissions"] = permissions
                        _save_roles(roles)
                return True
        return False


def get_role_permissions(role_id_or_name):
    role_data = get_role(role_id_or_name)
    if role_data is None:
        return None
    return role_data.get("permissions", [])


def remove_role_permission(role_id_or_name, permission):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                permissions = role_data.get("permissions", [])
                if permission in permissions:
                    permissions.remove(permission)
                    roles[role_name]["permissions"] = permissions
                    _save_roles(roles)
                    return True
        return False


def can_role_mention_role(user_roles, target_role):
    if "owner" in user_roles:
        return True

    target_role_data = get_role(target_role)
    if target_role_data is None:
        return True

    permissions = target_role_data.get("permissions", [])

    mention_permission = None
    if isinstance(permissions, dict):
        mention_permission = permissions.get("mention_roles")
    elif isinstance(permissions, list):
        pass

    if mention_permission is None:
        return True

    if isinstance(mention_permission, str):
        return mention_permission in user_roles

    if isinstance(mention_permission, list):
        return any(role in user_roles for role in mention_permission)

    if isinstance(mention_permission, bool):
        return mention_permission

    return True


def get_hoisted_roles():
    with _lock:
        roles = _get_roles_cache()
        result = []
        for role_name, role_data in roles.items():
            if role_data.get("hoisted"):
                result.append({"name": role_name, **role_data})
        return result


def is_role_hoisted(role_id_or_name):
    role_data = get_role(role_id_or_name)
    if role_data is None:
        return False
    return role_data.get("hoisted", False)


def is_role_self_assignable(role_id_or_name):
    role_data = get_role(role_id_or_name)
    if role_data is None:
        return False
    return role_data.get("self_assignable", False)


def get_self_assignable_roles():
    with _lock:
        roles = _get_roles_cache()
        result = {}
        for role_name, role_data in roles.items():
            if role_data.get("self_assignable", False):
                result[role_name] = role_data
        return result


def set_role_self_assignable(role_id_or_name, value):
    with _lock:
        roles = _get_roles_cache()
        for role_name, role_data in roles.items():
            if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                roles[role_name]["self_assignable"] = value
                _save_roles(roles)
                return True
        return False


def can_be_self_assignable(role_id_or_name):
    role = get_role(role_id_or_name)
    if role:
        return role.get("name") not in PROTECTED_ROLES
    return role_id_or_name not in PROTECTED_ROLES


def reorder_roles(role_order):
    with _lock:
        roles = _get_roles_cache()
        for i, role_id_or_name in enumerate(role_order):
            found = False
            for role_name, role_data in roles.items():
                if role_data.get("id") == role_id_or_name or role_name == role_id_or_name:
                    roles[role_name]["position"] = i
                    found = True
                    break
            if not found:
                return False
        _save_roles(roles)
        return True
