import asyncio, websockets, json, os, mimetypes, secrets
from urllib.parse import urlsplit, unquote
from websockets.datastructures import Headers
from websockets.http11 import Request, Response, d, parse_headers, parse_line
from handlers.websocket_utils import send_to_client, heartbeat, broadcast_to_all, broadcast_to_all_except, broadcast_to_channel_except, broadcast_to_voice_channel_with_viewers
from handlers.auth import handle_authentication
from handlers import message as message_handler
from handlers.rate_limiter import RateLimiter
from db import serverEmojis, push as push_db
import watchers
from plugin_manager import PluginManager
from logger import Logger
import slash_handlers


def _patch_websockets_request_parse():
    if getattr(Request, "_originchats_http_methods_patched", False):
        return

    @classmethod
    def _originchats_parse_request(cls, read_line):
        try:
            request_line = yield from parse_line(read_line)
        except EOFError as exc:
            raise EOFError("connection closed while reading HTTP request line") from exc

        # normalize potential bytearray
        request_line = bytes(request_line)

        try:
            method, raw_path, protocol = request_line.split(b" ", 2)
        except ValueError:
            raise ValueError(f"invalid HTTP request line: {d(request_line)}") from None

        if protocol != b"HTTP/1.1":
            raise ValueError(
                f"unsupported protocol; expected HTTP/1.1: {d(request_line)}"
            )
        if method not in {b"GET", b"HEAD", b"OPTIONS"}:
            raise ValueError(f"unsupported HTTP method; expected GET; got {d(method)}")

        path = raw_path.decode("ascii", "surrogateescape")
        headers = yield from parse_headers(read_line)

        if "Transfer-Encoding" in headers:
            raise NotImplementedError("transfer codings aren't supported")

        content_length = headers.get("Content-Length")
        if content_length not in (None, "0"):
            raise ValueError("unsupported request body")

        request = cls(path, headers)
        setattr(request, "method", method.decode("ascii", "surrogateescape"))
        return request

    setattr(Request, "parse", _originchats_parse_request)
    setattr(Request, "_originchats_http_methods_patched", True)


_patch_websockets_request_parse()

class OriginChatsServer:
    """OriginChats WebSocket server"""
    
    def __init__(self, config_path="config.json"):
        # Load configuration
        with open(os.path.join(os.path.dirname(__file__), config_path), "r") as f:
            self.config = json.load(f)
        
        # Server state
        self.connected_clients = set()
        self.connected_usernames = {}
        self.version = self.config["service"]["version"]
        self.heartbeat_interval = 30
        self.main_event_loop = None
        self.file_observer = None
        self.slash_commands = {}
        
        self.voice_channels = {}
        self.server_assets_dir = os.path.join(os.path.dirname(__file__), "db", "serverAssets")
        os.makedirs(self.server_assets_dir, exist_ok=True)
        self.server_asset_files = {}
        
        # Initialize rate limiter if enabled
        rate_config = self.config.get("rate_limiting", {})
        if rate_config.get("enabled", False):
            self.rate_limiter = RateLimiter(
                messages_per_minute=rate_config.get("messages_per_minute", 30),
                burst_limit=rate_config.get("burst_limit", 5),
                cooldown_seconds=rate_config.get("cooldown_seconds", 60)
            )
        else:
            self.rate_limiter = None
        
        # Initialize plugin manager
        self.plugin_manager = PluginManager()
        self._configure_server_assets()
        self.capabilities = self._detect_capabilities()
        self._register_server_slash_commands()

        # Cleanup stale push subscriptions on startup
        removed = push_db.cleanup_stale_subscriptions()
        if removed > 0:
            Logger.info(f"Cleaned up {removed} stale push subscriptions (inactive > 6 months)")

        Logger.info(f"OriginChats WebSocket Server v{self.version} initialized")
        if self.rate_limiter:
            Logger.info(f"Rate limiting enabled: {rate_config.get('messages_per_minute', 30)} msg/min, burst: {rate_config.get('burst_limit', 5)}")
        else:
            Logger.warning("Rate limiting disabled")

    def _register_server_slash_commands(self):
        """Register server-side slash commands as 'originChats' user"""
        server_commands = slash_handlers.get_all_command_info()
        if not server_commands:
            Logger.warning("No server slash commands found")
            return

        registered_commands = []
        for cmd_info in server_commands:
            cmd_name = cmd_info.get("name")
            if not cmd_name:
                continue

            self.slash_commands[f"server_{cmd_name}"] = {
                "command": type('obj', (object,), {
                    "name": cmd_name,
                    "description": cmd_info.get("description", ""),
                    "options": cmd_info.get("options", []),
                    "whitelistRoles": cmd_info.get("whitelistRoles"),
                    "blacklistRoles": cmd_info.get("blacklistRoles"),
                    "ephemeral": cmd_info.get("ephemeral", False)
                })(),
                "user_id": "originChats",
                "username": "originChats"
            }

            registered_commands.append({
                "name": cmd_name,
                "description": cmd_info.get("description", ""),
                "options": cmd_info.get("options", []),
                "whitelistRoles": cmd_info.get("whitelistRoles"),
                "blacklistRoles": cmd_info.get("blacklistRoles"),
                "ephemeral": cmd_info.get("ephemeral", False),
                "registeredBy": "originChats"
            })

        self._server_slash_commands = registered_commands
        Logger.success(f"Registered {len(registered_commands)} server slash commands")

    def _detect_capabilities(self):
        """Build the list of supported commands from the docs/commands directory."""
        commands_dir = os.path.join(os.path.dirname(__file__), "docs", "commands")
        if not os.path.isdir(commands_dir):
            Logger.warning("docs/commands directory not found; capabilities list will be empty")
            return []
        capabilities = sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(commands_dir)
            if f.endswith(".md") and not f.startswith(".")
        )
        Logger.info(f"Detected {len(capabilities)} capabilities from docs/commands")
        return capabilities

    def _normalize_public_base_url(self):
        base_url = self.config.get("server", {}).get("url")

        if base_url:
            base_url = base_url.strip().lower()

            secure = base_url.startswith("wss://") or base_url.startswith("https://")
            base_url = base_url.split("://", 1)[-1]

            suffix = "s" if secure else ""
            return f"http{suffix}://{base_url.rstrip('/')}"

        host = self.config.get("websocket", {}).get("host", "127.0.0.1")
        port = self.config.get("websocket", {}).get("port", 5613)
        return f"http://{host}:{port}"

    def _join_public_url(self, path):
        return f"{self._normalize_public_base_url().rstrip('/')}/{path.lstrip('/')}"

    def _resolve_server_asset_path(self, file_path):
        if not file_path or not isinstance(file_path, str):
            return None

        normalized_path = os.path.normpath(file_path)
        if not os.path.isabs(normalized_path):
            normalized_path = os.path.normpath(os.path.join(os.path.dirname(__file__), normalized_path))

        if not os.path.isfile(normalized_path):
            return None

        content_type, _ = mimetypes.guess_type(normalized_path)
        if not content_type or not content_type.startswith("image/"):
            return None

        return normalized_path

    def _register_server_asset(self, asset_name):
        if "server" not in self.config:
            return
        
        asset_value = self.config["server"].get(asset_name)
        if not asset_value or not isinstance(asset_value, str):
            return

        if "://" in asset_value:
            return

        asset_name_only = os.path.basename(asset_value)
        asset_path = os.path.join(self.server_assets_dir, asset_name_only)
        if not os.path.isfile(asset_path):
            Logger.warning(f"Server {asset_name} asset missing in db/serverAssets: {asset_name_only}")
            return

        self.server_asset_files[asset_name] = asset_path
        self.config["server"][asset_name] = self._join_public_url(f"/server-assets/{asset_name}")

    def _configure_server_assets(self):
        self._register_server_asset("icon")
        self._register_server_asset("banner")

    def _resolve_emoji_file_path(self, file_name):
        """
        Resolve and validate custom emoji file path in db/serverEmojis.
        Returns absolute file path or None when invalid/missing.
        """
        if not file_name:
            return None

        if file_name != os.path.basename(file_name) or file_name.startswith("."):
            return None

        if not serverEmojis.is_allowed_file_type(file_name):
            return None

        emoji_dir = os.path.join(os.path.dirname(__file__), "db", "serverEmojis")
        file_path = os.path.normpath(os.path.join(emoji_dir, file_name))
        emoji_dir_norm = os.path.normpath(emoji_dir)

        if not file_path.startswith(emoji_dir_norm + os.sep):
            return None

        if not os.path.isfile(file_path):
            return None

        return file_path

    def _response_headers(self, extra_headers=None):
        headers = list(extra_headers or [])
        headers.extend([
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization, Range"),
            ("Access-Control-Expose-Headers", "Content-Length, Content-Type, Cache-Control"),
        ])
        return Headers(headers)

    def _empty_response(self, status, reason, extra_headers=None):
        headers = list(extra_headers or [])
        headers.append(("Content-Length", "0"))
        return Response(status, reason, self._response_headers(headers), b"")

    def _serve_file_response(self, file_path, request_method="GET", cache_control="public, max-age=3600"):
        body = b""
        if request_method != "HEAD":
            with open(file_path, "rb") as f:
                body = f.read()

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        return Response(
            200,
            "OK",
            self._response_headers(
                [
                    ("Content-Type", content_type),
                    ("Content-Length", str(os.path.getsize(file_path))),
                    ("Cache-Control", cache_control),
                ]
            ),
            body,
        )

    def _resolve_server_asset_request(self, asset_name):
        return self.server_asset_files.get(asset_name)

    async def _process_http_request(self, connection, request):
        """
        Serve HTTP asset files on the same socket as WebSocket traffic.
        """
        request_method = getattr(request, "method", "GET").upper()
        if request_method == "OPTIONS":
            return self._empty_response(204, "No Content")
        if request_method not in {"GET", "HEAD"}:
            return self._empty_response(
                405,
                "Method Not Allowed",
                [("Allow", "GET, HEAD, OPTIONS")],
            )

        upgrade = request.headers.get("Upgrade", "")
        connection_hdr = request.headers.get("Connection", "")
        connection_tokens = {token.strip().lower() for token in connection_hdr.split(",") if token.strip()}
        is_websocket_upgrade = upgrade.lower() == "websocket" and "upgrade" in connection_tokens
        if is_websocket_upgrade:
            return None

        path = urlsplit(request.path).path
        if path in ("/", "/index.html"):
            index_path = os.path.join(os.path.dirname(__file__), "index.html")
            if not os.path.isfile(index_path):
                return Response(
                    404,
                    "Not Found",
                    self._response_headers([("Content-Type", "text/plain; charset=utf-8")]),
                    b"" if request_method == "HEAD" else b"index.html not found",
                )
            return self._serve_file_response(index_path, request_method=request_method, cache_control="no-cache")

        if path.startswith("/emojis/"):
            file_name = unquote(path[len("/emojis/"):]).strip()
            file_path = self._resolve_emoji_file_path(file_name)
            if not file_path:
                return Response(
                    404,
                    "Not Found",
                    self._response_headers([("Content-Type", "text/plain; charset=utf-8")]),
                    b"" if request_method == "HEAD" else b"Emoji not found",
                )
            return self._serve_file_response(file_path, request_method=request_method, cache_control="public, max-age=3600")

        if path.startswith("/server-assets/"):
            asset_name = path[len("/server-assets/"):].strip("/")
            file_path = self._resolve_server_asset_request(asset_name)
            if not file_path:
                return Response(
                    404,
                    "Not Found",
                    self._response_headers([("Content-Type", "text/plain; charset=utf-8")]),
                    b"" if request_method == "HEAD" else b"Server asset not found",
                )
            return self._serve_file_response(file_path, request_method=request_method, cache_control="public, max-age=3600")

        return Response(
            404,
            "Not Found",
            self._response_headers([("Content-Type", "text/plain; charset=utf-8")]),
            b"" if request_method == "HEAD" else b"Not found",
        )

    async def handle_client(self, websocket):
        """WebSocket connection handler"""
        # Get client info
        headers = websocket.request.headers
        client_ip = headers.get('CF-Connecting-IP') or headers.get('X-Forwarded-For') or websocket.remote_address[0]
        Logger.add(f"New connection from {client_ip}")
        
        # Add to connected clients
        self.connected_clients.add(websocket)
        Logger.info(f"Total connected clients: {len(self.connected_clients)}")
        
        # Start heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat(websocket, self.heartbeat_interval))
        
        try:
            # Generate a unique validator key for this connection
            connection_validator_key = "originChats-" + secrets.token_urlsafe(24)
            websocket.validator_key = connection_validator_key

            # Send handshake message
            await send_to_client(websocket, {
                "cmd": "handshake",
                "val": {
                    "server": self.config["server"],
                    "limits": self.config["limits"],
                    "version": "1.1.0",
                    "validator_key": connection_validator_key,
                    "capabilities": self.capabilities
                }
            })

            # Send server slash commands to the client
            if hasattr(self, '_server_slash_commands') and self._server_slash_commands:
                await send_to_client(websocket, {
                    "cmd": "slash_add",
                    "commands": self._server_slash_commands
                })
                
            # Keep connection open and handle client messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    # Handle authentication
                    if data.get("cmd") == "auth" and not getattr(websocket, "authenticated", False):
                        # Create server data object for authentication
                        auth_server_data = {
                            "connected_clients": self.connected_clients,
                            "connected_usernames": self.connected_usernames,
                            "config": self.config,
                            "plugin_manager": self.plugin_manager,
                            "rate_limiter": self.rate_limiter
                        }
                        await handle_authentication(
                            websocket, data, self.config,
                            self.connected_clients, client_ip, auth_server_data,
                            validator_key=getattr(websocket, "validator_key", None)
                        )
                        continue

                    # Require authentication for other commands
                    if not getattr(websocket, "authenticated", False):
                        await send_to_client(websocket, {"cmd": "auth_error", "val": "Authentication required"})
                        continue

                    # Create server data object for message handler
                    server_data = {
                        "connected_clients": self.connected_clients,
                        "connected_usernames": self.connected_usernames,
                        "config": self.config,
                        "plugin_manager": self.plugin_manager,
                        "rate_limiter": self.rate_limiter,
                        "send_to_client": send_to_client,
                        "slash_commands": self.slash_commands,
                        "voice_channels": self.voice_channels
                    }

                    listener = data.get("listener")
                    if listener and not isinstance(listener, str):
                        Logger.warning(f"Invalid listener type: {type(listener)}")
                        listener = None
                    # Handle message
                    response = await message_handler.handle(websocket, data, server_data)
                    
                    if not response:
                        Logger.warning(f"No response for message: {data}")
                        continue
                    
                    if response.get("global", False):
                        # Check if this is a channel-specific message
                        if response.get("channel"):
                            # Broadcast only to users who have access to the channel
                            await broadcast_to_channel_except(self.connected_clients, response, response["channel"], websocket)
                        else:
                            # Broadcast to all clients if no channel specified
                            await broadcast_to_all_except(self.connected_clients, response, websocket)
                        
                        if listener:
                            response["listener"] = listener
                        await send_to_client(websocket, response)
                        continue

                    if response:
                        if listener:
                            response["listener"] = listener
                        await send_to_client(websocket, response)

                except json.JSONDecodeError:
                    Logger.error(f"Received invalid JSON: {message[:50]}...")
                except Exception as e:
                    Logger.error(f"Error processing message: {str(e)}")
                    
        except websockets.exceptions.ConnectionClosed:
            Logger.info(f"Connection closed by {client_ip}")
        except Exception as e:
            Logger.error(f"Error handling connection: {str(e)}")
        finally:
            heartbeat_task.cancel()
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
                Logger.delete(f"Client {client_ip} removed. {len(self.connected_clients)} clients remaining")

                username = getattr(websocket, "username", "")

                if getattr(websocket, "authenticated", False):
                    user_id = getattr(websocket, "user_id", None)
                    current_voice_channel = getattr(websocket, "voice_channel", None)

                    if user_id and current_voice_channel:
                        if current_voice_channel in self.voice_channels and user_id in self.voice_channels[current_voice_channel]:
                            msg = {"cmd": "voice_user_left", "channel": current_voice_channel, "username": username}
                            await broadcast_to_voice_channel_with_viewers(
                                self.connected_clients,
                                self.voice_channels,
                                msg,
                                msg,
                                current_voice_channel
                            )

                            del self.voice_channels[current_voice_channel][user_id]

                            if not self.voice_channels[current_voice_channel]:
                                del self.voice_channels[current_voice_channel]

                    ws_id = id(websocket)
                    if ws_id in self.slash_commands:
                        command_names = list(self.slash_commands[ws_id].keys())
                        if command_names:
                            await broadcast_to_all(self.connected_clients, {
                                "cmd": "slash_remove",
                                "commands": command_names
                            })
                            Logger.info(f"Removed {len(command_names)} slash commands for connection {ws_id}")
                        del self.slash_commands[ws_id]

                    if username in self.connected_usernames:
                        self.connected_usernames[username] -= 1
                        if self.connected_usernames[username] <= 0:
                            del self.connected_usernames[username]
                            await broadcast_to_all(self.connected_clients, {
                                "cmd": "user_disconnect",
                                "username": username
                            })
                            Logger.success(f"Broadcast user_disconnect: {username}")
                        else:
                            Logger.info(f"User {username} still has {self.connected_usernames[username]} active connection(s)")
    
    async def broadcast_wrapper(self, message):
        """Wrapper for broadcast_to_all to maintain compatibility with watchers"""
        await broadcast_to_all(self.connected_clients, message)
    
    async def start_server(self):
        """Start the WebSocket server"""
        # Store the main event loop for use in other threads
        self.main_event_loop = asyncio.get_event_loop()

        # Setup file watchers for users.json and channels.json
        self.file_observer = watchers.setup_file_watchers(self.broadcast_wrapper, self.main_event_loop, lambda: self.connected_clients)

        port = self.config.get("websocket", {}).get("port", 5613)
        host = self.config.get("websocket", {}).get("host", "127.0.0.1")
        
        Logger.info(f"Starting WebSocket server on {host}:{port}")
        
        # Trigger server_start event for plugins
        server_data = {
            "connected_clients": self.connected_clients,
            "config": self.config,
            "plugin_manager": self.plugin_manager,
            "rate_limiter": self.rate_limiter
        }
        self.plugin_manager.trigger_event("server_start", None, {}, server_data)
        
        try:
            async with websockets.serve(
                self.handle_client,
                host,
                port,
                ping_interval=None,
                process_request=self._process_http_request,
            ):
                Logger.success(f"WebSocket server running at ws://{host}:{port}")
                
                # Keep the server running
                await asyncio.Future()
        finally:
            # Stop file watcher when server stops
            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join()
                Logger.info("File watcher stopped")
