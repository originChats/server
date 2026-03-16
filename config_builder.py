from copy import deepcopy


DEFAULT_CONFIG = {
    "limits": {
        "post_content": 2000,
        "search_results": 30,
    },
    "uploads": {
        "emoji_allowed_file_types": ["gif", "jpg", "jpeg", "png"],
    },
    "rate_limiting": {
        "enabled": True,
        "messages_per_minute": 60,
        "burst_limit": 10,
        "cooldown_seconds": 30,
    },
    "DB": {
        "channels": "db/channels.json",
        "users": {
            "file": "db/users.json",
            "default": {
                "roles": ["user"],
            },
        },
    },
    "websocket": {
        "host": "127.0.0.1",
        "port": 5613,
    },
    "service": {
        "name": "OriginChats",
        "version": "1.0.0",
    },
    "server": {
        "name": "My OriginChats Server",
        "owner": {
            "name": "Admin",
        },
    },
}


def _deep_merge(base, overrides):
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
            continue
        base[key] = value
    return base


def _remove_none_values(data):
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, dict):
            nested = _remove_none_values(value)
            if nested:
                cleaned[key] = nested
            continue
        if value is not None:
            cleaned[key] = value
    return cleaned


def build_config(overrides=None):
    config = deepcopy(DEFAULT_CONFIG)

    if overrides:
        _deep_merge(config, _remove_none_values(overrides))

    return config
