import json
import os
from copy import deepcopy
from typing import Any, TypeVar, overload

from config_builder import DEFAULT_CONFIG


_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_ROOT_DIR, "config.json")
_cached_config = None
_cached_mtime = None
ConfigDict = dict[str, Any]
T = TypeVar("T")


def _load_config_from_disk() -> ConfigDict:
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return deepcopy(DEFAULT_CONFIG)


def get_config(force_reload: bool = False) -> ConfigDict:
    global _cached_config, _cached_mtime

    try:
        current_mtime = os.path.getmtime(_CONFIG_PATH)
    except FileNotFoundError:
        current_mtime = None

    if force_reload or _cached_config is None or current_mtime != _cached_mtime:
        _cached_config = _load_config_from_disk()
        _cached_mtime = current_mtime

    return _cached_config


@overload
def get_config_value(*path: str, default: T, config: ConfigDict | None = None) -> T: ...


@overload
def get_config_value(*path: str, default: None = None, config: ConfigDict | None = None) -> Any | None: ...


def get_config_value(*path: str, default: T | None = None, config: ConfigDict | None = None) -> T | Any | None:
    current = get_config() if config is None else config

    for key in path:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]

    return current
