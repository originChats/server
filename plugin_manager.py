import os
import importlib.util
import inspect
from typing import Dict, List, Any, Callable, Optional
from logger import Logger

class PluginManager:
    """Manages loading and execution of plugins"""
    
    def __init__(self, plugins_dir="plugins"):
        # Make plugins_dir relative to this file's location
        if not os.path.isabs(plugins_dir):
            self.plugins_dir = os.path.join(os.path.dirname(__file__), plugins_dir)
        else:
            self.plugins_dir = plugins_dir
        self.loaded_plugins = {}
        self.event_handlers = {}
        self.load_plugins()
    
    def load_plugins(self):
        """Discover and load all plugins from the plugins directory"""
        if not os.path.exists(self.plugins_dir):
            Logger.warning(f"Plugins directory '{self.plugins_dir}' not found")
            return
        
        plugin_files = [f for f in os.listdir(self.plugins_dir) 
                       if f.endswith('.py') and not f.startswith('__')]
        
        for plugin_file in plugin_files:
            plugin_name = plugin_file[:-3]  # Remove .py extension
            plugin_path = os.path.join(self.plugins_dir, plugin_file)
            
            try:
                self._load_plugin(plugin_name, plugin_path)
            except Exception as e:
                Logger.error(f"Failed to load plugin '{plugin_name}': {str(e)}")
    
    def _load_plugin(self, plugin_name: str, plugin_path: str):
        """Load a single plugin"""
        # Load the module
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        if spec is None or spec.loader is None:
            Logger.error(f"Could not load spec for plugin '{plugin_name}' at '{plugin_path}'")
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check if plugin has required functions
        if not hasattr(module, 'getInfo'):
            Logger.warning(f"Plugin '{plugin_name}' missing getInfo() function")
            return
        
        # Get plugin info
        plugin_info = module.getInfo()
        if not isinstance(plugin_info, dict) or 'handles' not in plugin_info:
            Logger.warning(f"Plugin '{plugin_name}' has invalid getInfo() return value")
            return
        
        # Store the plugin
        self.loaded_plugins[plugin_name] = {
            'module': module,
            'info': plugin_info,
            'path': plugin_path
        }
        
        # Register event handlers
        for event in plugin_info['handles']:
            handler_name = f"on_{event}"
            if hasattr(module, handler_name):
                if event not in self.event_handlers:
                    self.event_handlers[event] = []
                self.event_handlers[event].append({
                    'plugin_name': plugin_name,
                    'handler': getattr(module, handler_name),
                    'required_permission': getattr(module, 'required_permission', [])
                })
                Logger.add(f"Registered handler '{handler_name}' for event '{event}' from plugin '{plugin_name}'")
            else:
                Logger.warning(f"Plugin '{plugin_name}' handles '{event}' but missing '{handler_name}' function")
        
        Logger.success(f"Loaded plugin '{plugin_name}': {plugin_info.get('name', 'Unknown')}")
        Logger.info(f"Handles events: {plugin_info['handles']}")
    
    def get_loaded_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all loaded plugins"""
        return {name: plugin['info'] for name, plugin in self.loaded_plugins.items()}
    
    def trigger_event(self, event: str, ws, message_data: Dict[str, Any], server_data: Optional[Dict[str, Any]] = None):
        """Trigger an event for all plugins that handle it"""

        if event not in self.event_handlers:
            return

        for handler_info in self.event_handlers[event]:
            try:

                # Check permissions if required
                required_permissions = handler_info.get('required_permission', [])
                if required_permissions:
                    from db import users
                    from handlers.websocket_utils import _get_ws_attr
                    username = _get_ws_attr(ws, server_data, "username")
                    user_roles = users.get_user_roles(username)
                    if not user_roles or not any(role in user_roles for role in required_permissions):
                        continue
                
                # Call the handler
                handler = handler_info['handler']
                
                # Check handler signature to determine how to call it
                sig = inspect.signature(handler)
                
                # Check if handler is async
                if inspect.iscoroutinefunction(handler):
                    # For async handlers, we need to schedule them
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if len(sig.parameters) == 2:
                            asyncio.create_task(handler(ws, message_data))
                        elif len(sig.parameters) == 3:
                            asyncio.create_task(handler(ws, message_data, server_data))
                        else:
                            asyncio.create_task(handler(ws, message_data))
                    except RuntimeError:
                        # No event loop running, create one
                        if len(sig.parameters) == 2:
                            asyncio.run(handler(ws, message_data))
                        elif len(sig.parameters) == 3:
                            asyncio.run(handler(ws, message_data, server_data))
                        else:
                            asyncio.run(handler(ws, message_data))
                else:
                    # Synchronous handler
                    if len(sig.parameters) == 2:
                        handler(ws, message_data)
                    elif len(sig.parameters) == 3:
                        handler(ws, message_data, server_data)
                    else:
                        # Fallback: try with ws and message_data
                        handler(ws, message_data)
                    
            except Exception as e:
                Logger.error(f"Error in plugin '{handler_info['plugin_name']}' handler: {str(e)}")
                import traceback
                traceback.print_exc()
    
    def reload_plugin(self, plugin_name: str):
        """Reload a specific plugin"""
        if plugin_name not in self.loaded_plugins:
            Logger.warning(f"Plugin '{plugin_name}' not found")
            return False
        
        plugin_path = self.loaded_plugins[plugin_name]['path']
        
        # Remove old handlers
        for event, handlers in self.event_handlers.items():
            self.event_handlers[event] = [h for h in handlers if h['plugin_name'] != plugin_name]
        
        # Remove old plugin
        del self.loaded_plugins[plugin_name]
        
        # Reload the plugin
        try:
            self._load_plugin(plugin_name, plugin_path)
            Logger.success(f"Reloaded plugin '{plugin_name}'")
            return True
        except Exception as e:
            Logger.error(f"Failed to reload plugin '{plugin_name}': {str(e)}")
            return False
    
    def reload_all_plugins(self):
        """Reload all plugins"""
        Logger.info("Reloading all plugins...")
        
        # Clear everything
        self.loaded_plugins.clear()
        self.event_handlers.clear()
        
        # Reload all plugins
        self.load_plugins()
        
        Logger.success(f"Reloaded {len(self.loaded_plugins)} plugins")
