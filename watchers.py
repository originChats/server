import asyncio
import json
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from db import users, channels, roles
from logger import Logger
from handlers.websocket_utils import send_to_client

class FileWatcher(FileSystemEventHandler):
    """File system event handler for watching JSON files"""

    def __init__(self, broadcast_func, main_loop, connected_clients_getter, server_data_getter=None):
        self.broadcast_func = broadcast_func
        self.main_loop = main_loop
        self.connected_clients_getter = connected_clients_getter
        self.server_data_getter = server_data_getter

        # Cache for tracking changes
        self._users_cache = {}
        self._channels_cache = []

        # Initialize caches
        self._load_initial_state()
        super().__init__()
    
    def _load_initial_state(self):
        """Load initial state of files to track changes"""
        try:
            with open(users.users_index, 'r') as f:
                self._users_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._users_cache = {}
        
        try:
            with open(channels.channels_index, 'r') as f:
                self._channels_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._channels_cache = []
    
    def on_modified(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)
        # Handle users.json changes
        if filename == 'users.json':
            Logger.edit(f"Users file changed: {event.src_path}")
            asyncio.run_coroutine_threadsafe(
                self._handle_users_change(),
                self.main_loop
            )

        # Handle roles.json changes
        elif filename == 'roles.json':
            Logger.edit(f"Roles file changed: {event.src_path}")
            asyncio.run_coroutine_threadsafe(
                self._handle_roles_change(),
                self.main_loop
            )

        # Handle channels.json changes
        elif filename == 'channels.json':
            Logger.edit(f"Channels file changed: {event.src_path}")
            asyncio.run_coroutine_threadsafe(
                self._handle_channels_change(),
                self.main_loop
            )
    
    async def _handle_users_change(self):
        try:
            await self.broadcast_func({
                "cmd": "users_list",
                "users": users.get_users()
            })

            self._broadcast_nickname_changes()

        except Exception as e:
            Logger.error(f"Error handling users.json change: {e}")

    async def _handle_roles_change(self):
        try:
            roles.reload_roles()
            await self.broadcast_func({
                "cmd": "roles_list",
                "roles": roles.get_all_roles()
            })
        except Exception as e:
            Logger.error(f"Error handling roles.json change: {e}")
    
    async def _handle_channels_change(self):
        """Handle channels.json file changes"""
        try:
            # Reload server's channel cache
            channels._load_channels_index()

            connected_clients = self.connected_clients_getter()
            disconnected = set()

            server_data = self.server_data_getter() if self.server_data_getter else {}
            _ws_data_all = server_data.get("_ws_data", {}) if server_data else {}

            for ws in connected_clients.copy():
                ws_data = _ws_data_all.get(id(ws), {})

                if not ws_data.get("authenticated", False):
                    continue

                user_id = ws_data.get("user_id")
                if not user_id:
                    continue

                user_data = users.get_user(user_id)
                if not user_data:
                    continue

                user_roles = user_data.get("roles", [])
                filtered_channels = channels.get_all_channels_for_roles(user_roles)

                success = await send_to_client(ws, {
                    "cmd": "channels_get",
                    "val": filtered_channels
                })
                if not success:
                    disconnected.add(ws)

            if disconnected:
                Logger.delete(f"Removed {len(disconnected)} disconnected clients during channels broadcast")

        except Exception as e:
            Logger.error(f"Error handling channels.json change: {e}")

    def _broadcast_nickname_changes(self):
        """Compare old and new users to detect and broadcast nickname changes"""
        try:
            old_users = self._users_cache
            new_users = users._get_users_cache()

            for user_id, new_data in new_users.items():
                old_data = old_users.get(user_id, {})
                old_nick = old_data.get("nickname")
                new_nick = new_data.get("nickname")
                username = new_data.get("username", user_id)

                if old_nick != new_nick:
                    if new_nick:
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast_func({
                                "cmd": "nickname_update",
                                "user": user_id,
                                "username": username,
                                "nickname": new_nick
                            }),
                            self.main_loop
                        )
                    else:
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast_func({
                                "cmd": "nickname_remove",
                                "user": user_id,
                                "username": username
                            }),
                            self.main_loop
                        )

            self._users_cache = dict(new_users)

        except Exception as e:
            Logger.error(f"Error broadcasting nickname changes: {e}")

def setup_file_watchers(broadcast_func, main_loop, connected_clients_getter, server_data_getter=None):
    """Setup file watchers for users.json and channels.json"""

    # Get the database directory
    db_dir = os.path.dirname(users.users_index)

    # Create event handler
    event_handler = FileWatcher(broadcast_func, main_loop, connected_clients_getter, server_data_getter)

    # Create observer
    observer = Observer()
    observer.schedule(event_handler, db_dir, recursive=False)

    # Start watching
    observer.start()
    Logger.success(f"File watcher started for directory: {db_dir}")

    return observer
