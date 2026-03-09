from copy import deepcopy


DEFAULT_CONFIG = {
    "limits": {
        "post_content": 2000,
        "search_results": 30,
    },
    "uploads": {
        "emoji_allowed_file_types": ["gif", "jpg", "jpeg"],
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
    "rotur": {
        "validate_url": "https://social.rotur.dev/validate",
        "validate_key": "your_key_here",
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


def build_config(
    server_name=None,
    owner_name=None,
    ws_host=None,
    ws_port=None,
    rotur_url=None,
    rotur_key=None,
    max_message_length=None,
    search_results_limit=None,
    server_icon=None,
    server_url=None,
    emoji_allowed_file_types=None,
    overrides=None,
):
    config = deepcopy(DEFAULT_CONFIG)

    direct_updates = {
        "limits": {
            "post_content": max_message_length,
            "search_results": search_results_limit,
        },
        "websocket": {
            "host": ws_host,
            "port": ws_port,
        },
        "rotur": {
            "validate_url": rotur_url,
            "validate_key": rotur_key,
        },
        "server": {
            "name": server_name,
            "owner": {
                "name": owner_name,
            },
        },
        "uploads": {
            "emoji_allowed_file_types": emoji_allowed_file_types,
        },
    }

    for section, values in direct_updates.items():
        if not isinstance(values, dict):
            continue
        for key, value in list(values.items()):
            if isinstance(value, dict):
                nested_values = {nested_key: nested_value for nested_key, nested_value in value.items() if nested_value is not None}
                if nested_values:
                    config[section][key].update(nested_values)
                continue
            if value is not None:
                config[section][key] = value

    if server_icon:
        config["server"]["icon"] = server_icon
    else:
        config["server"].pop("icon", None)

    if server_url:
        config["server"]["url"] = server_url
    else:
        config["server"].pop("url", None)

    if overrides:
        _deep_merge(config, overrides)

    return config
