import json
import os

from logger import Logger


def load_plugin_config(config_filename: str, defaults: dict) -> dict:
    config_path = os.path.join(os.path.dirname(__file__), config_filename)
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        Logger.warning(f"{config_filename} not found, using defaults")
        return defaults


def save_plugin_config(config_filename: str, config: dict) -> None:
    config_path = os.path.join(os.path.dirname(__file__), config_filename)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
