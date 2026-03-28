import json
import os
import threading
from typing import Optional, Any

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
_lock = threading.RLock()


def get_server_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def save_server_config(config: dict) -> bool:
    with _lock:
        try:
            with open(_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


def get_server_info() -> dict:
    config = get_server_config()
    return {
        "name": config.get("server", {}).get("name", ""),
        "icon": config.get("server", {}).get("icon", ""),
        "banner": config.get("server", {}).get("banner", "")
    }


def update_server_info(name: Optional[str] = None, icon: Optional[str] = None, banner: Optional[str] = None) -> dict:
    with _lock:
        config = get_server_config()
        
        if "server" not in config:
            config["server"] = {}
        
        if name is not None:
            config["server"]["name"] = name
        if icon is not None:
            config["server"]["icon"] = icon
        if banner is not None:
            config["server"]["banner"] = banner
        
        save_server_config(config)
        
        return {
            "name": config["server"].get("name", ""),
            "icon": config["server"].get("icon", ""),
            "banner": config["server"].get("banner", "")
        }
