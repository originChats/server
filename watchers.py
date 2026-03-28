import asyncio
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from db import users, channels, roles
from logger import Logger
from handlers.websocket_utils import send_to_client


class FileWatcher(FileSystemEventHandler):
    """File system event handler for watching database files"""

    def __init__(self, broadcast_func, main_loop, connected_clients_getter, server_data_getter=None):
        self.broadcast_func = broadcast_func
        self.main_loop = main_loop
        self.connected_clients_getter = server_data_getter
        self._users_cache = {}
        self._channels_cache = []
        self._roles_cache = {}
        self._load_initial_state()
        super().__init__()

    def _load_initial_state(self):
        """Load initial state from database"""
        try:
            self._users_cache = users.reload_users()
        except Exception:
            self._users_cache = {}

        try:
            self._channels_cache = channels._get_channels()
        except Exception:
            self._channels_cache = []

        try:
            self._roles_cache = {r["name"]: r for r in roles.get_all_roles()} if hasattr(roles, 'get_all_roles') else {}
        except Exception:
            self._roles_cache = {}

    def on_modified(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)

        # Don't watch WAL/shm files - they change on every write
        if filename.startswith('originchats.db-'):
            return

        if filename == 'originchats.db':
            Logger.edit(f"Database file changed: {event.src_path}")
            asyncio.run_coroutine_threadsafe(
                self._handle_database_change(),
                self.main_loop
            )

    async def _handle_database_change(self):
        # Don't broadcast users_list on every DB change - too noisy
        # Only broadcast specific changes when needed
        pass

    async def _handle_users_change(self):
        pass

    async def _handle_roles_change(self):
        pass

    async def _handle_channels_change(self):
        """Handle channels change"""
        try:
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
            Logger.error(f"Error handling channels change: {e}")

    def _broadcast_nickname_changes(self):
        """Compare old and new users to detect and broadcast nickname changes"""
        try:
            old_users = self._users_cache
            new_users = users.reload_users()

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
    """Setup file watchers for the database"""

    db_dir = os.path.join(os.path.dirname(__file__), 'db')

    event_handler = FileWatcher(broadcast_func, main_loop, connected_clients_getter, server_data_getter)

    observer = Observer()
    observer.schedule(event_handler, db_dir, recursive=False)

    observer.start()
    Logger.success(f"File watcher started for directory: {db_dir}")

    return observer
