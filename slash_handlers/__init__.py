import os
import importlib.util
import inspect
import asyncio
from typing import Dict, Any, Callable, Optional, List
from logger import Logger

_handlers_dir = os.path.dirname(os.path.abspath(__file__))
SERVER_SLASH_HANDLERS: Dict[str, Dict[str, Any]] = {}
_initialized = False


def _load_handlers():
    global SERVER_SLASH_HANDLERS, _initialized
    
    if _initialized:
        return
    
    if not os.path.exists(_handlers_dir):
        Logger.warning(f"slash_handlers directory '{_handlers_dir}' not found")
        return
    
    handler_files = [
        f for f in os.listdir(_handlers_dir)
        if f.endswith('.py') and not f.startswith('_')
    ]
    
    for handler_file in handler_files:
        handler_name = handler_file[:-3]
        handler_path = os.path.join(_handlers_dir, handler_file)
        
        try:
            _load_handler(handler_name, handler_path)
        except Exception as e:
            Logger.error(f"Failed to load slash handler '{handler_name}': {str(e)}")
    
    _initialized = True
    Logger.success(f"Loaded {len(SERVER_SLASH_HANDLERS)} server slash handlers")


def _load_handler(handler_name: str, handler_path: str):
    spec = importlib.util.spec_from_file_location(handler_name, handler_path)
    if spec is None or spec.loader is None:
        Logger.error(f"Could not load spec for handler '{handler_name}'")
        return
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    if not hasattr(module, 'get_command_info'):
        Logger.warning(f"Slash handler '{handler_name}' missing get_command_info()")
        return
    
    if not hasattr(module, 'handle'):
        Logger.warning(f"Slash handler '{handler_name}' missing handle()")
        return
    
    command_info = module.get_command_info()
    if not isinstance(command_info, dict) or 'name' not in command_info:
        Logger.warning(f"Slash handler '{handler_name}' has invalid get_command_info()")
        return
    
    cmd_name = command_info['name']
    
    SERVER_SLASH_HANDLERS[cmd_name] = {
        'info': command_info,
        'handler': module.handle,
        'is_async': inspect.iscoroutinefunction(module.handle)
    }
    
    Logger.info(f"Registered server slash command: /{cmd_name}")


def get_all_command_info() -> List[Dict[str, Any]]:
    if not _initialized:
        _load_handlers()
    
    commands = []
    for cmd_name, handler_data in SERVER_SLASH_HANDLERS.items():
        info = handler_data['info'].copy()
        commands.append(info)
    
    return commands


def get_handler(cmd_name: str) -> Optional[Callable]:
    if not _initialized:
        _load_handlers()
    
    handler_data = SERVER_SLASH_HANDLERS.get(cmd_name)
    if handler_data:
        return handler_data['handler']
    return None


def is_async_handler(cmd_name: str) -> bool:
    if not _initialized:
        _load_handlers()
    
    handler_data = SERVER_SLASH_HANDLERS.get(cmd_name)
    if handler_data:
        return handler_data.get('is_async', False)
    return False


def handler_exists(cmd_name: str) -> bool:
    if not _initialized:
        _load_handlers()
    
    return cmd_name in SERVER_SLASH_HANDLERS


def get_command_roles(cmd_name: str) -> Dict[str, Optional[List[str]]]:
    if not _initialized:
        _load_handlers()
    
    handler_data = SERVER_SLASH_HANDLERS.get(cmd_name)
    if not handler_data:
        return {'whitelist': None, 'blacklist': None}
    
    info = handler_data['info']
    return {
        'whitelist': info.get('whitelistRoles'),
        'blacklist': info.get('blacklistRoles')
    }


_load_handlers()
