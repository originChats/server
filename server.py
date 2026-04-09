import asyncio, json, os, secrets, uuid, time
from urllib.parse import unquote
from aiohttp import web
import aiohttp
from handlers.websocket_utils import send_to_client, heartbeat, broadcast_to_all, broadcast_to_all_except, broadcast_to_channel_except, broadcast_to_voice_channel_with_viewers, set_ws_data
from handlers.auth import handle_authentication, handle_cracked_auth, handle_cracked_register
from handlers import message as message_handler
from handlers.rate_limiter import RateLimiter
from handlers import github_webhook
from db import serverEmojis, push as push_db, webhooks as webhooks_db, channels, users, roles, attachments as attachments_db, permissions as permissions_db
import watchers
from plugin_manager import PluginManager
from logger import Logger
import slash_handlers
from constants import HEARTBEAT_INTERVAL


class OriginChatsServer:
    """OriginChats WebSocket server"""
    
    def __init__(self, config_path="config.json"):
        # Load configuration
        with open(os.path.join(os.path.dirname(__file__), config_path), "r") as f:
            self.config = json.load(f)

        self.connected_clients = set()
        self.connected_usernames = {}
        self._ws_data = {} # Store custom websocket data by ws id
        set_ws_data(self._ws_data)
        self.version = self.config["service"]["version"]
        self.heartbeat_interval = HEARTBEAT_INTERVAL
        self.main_event_loop = None
        self.file_observer = None
        self.slash_commands = {}
        
        self.voice_channels = {}
        self.server_assets_dir = os.path.join(os.path.dirname(__file__), "db", "serverAssets")
        os.makedirs(self.server_assets_dir, exist_ok=True)
        self.server_asset_files = {}

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

        # Cleanup expired attachments on startup
        attachment_config = self.config.get("attachments", {})
        if attachment_config.get("enabled", True):
            expired_count = attachments_db.cleanup_expired_attachments()
            if expired_count > 0:
                Logger.info(f"Cleaned up {expired_count} expired attachments")

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

        self.slash_commands["server"] = {}
        registered_commands = []
        for cmd_info in server_commands:
            cmd_name = cmd_info.get("name")
            if not cmd_name:
                continue

            self.slash_commands["server"][cmd_name] = {
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

    def _resolve_emoji_file_path_by_id(self, emoji_id):
        """
        Resolve emoji file path by emoji ID.
        Returns absolute file path or None if not found.
        """
        if not emoji_id:
            return None
        file_name = serverEmojis.get_emoji_file_name(str(emoji_id))
        if not file_name:
            return None
        return self._resolve_emoji_file_path(file_name)

    def _cors_headers(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS, POST",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Range",
            "Access-Control-Expose-Headers": "Content-Length, Content-Type, Cache-Control",
        }

    def _apply_cors(self, response):
        for k, v in self._cors_headers().items():
            response.headers[k] = v
        return response

    async def _route_options(self, request):
        return self._apply_cors(web.Response(status=204))

    async def _route_index(self, request):
        index_path = os.path.join(os.path.dirname(__file__), "index.html")
        if not os.path.isfile(index_path):
            return self._apply_cors(web.Response(status=404, text="index.html not found"))
        return self._apply_cors(web.FileResponse(index_path, headers={
            "Cache-Control": "no-cache",
            **self._cors_headers()
        }))

    async def _route_404(self, request):
        return self._apply_cors(web.Response(
            status=404,
            content_type="application/json",
            text=json.dumps({"error": "Not found"})
        ))

    async def _route_info(self, request):
        info = {
            "server": {
                "name": self.config.get("server", {}).get("name", ""),
                "icon": self.config.get("server", {}).get("icon", ""),
                "banner": self.config.get("server", {}).get("banner", ""),
                "owner": self.config.get("server", {}).get("owner", {})
            },
            "stats": {
                "total_users": users.count_users(),
                "connected_users": len(self.connected_clients),
                "online_users": len(self.connected_usernames),
                "total_channels": len(channels._load_channels_index()),
                "total_roles": roles.count_roles()
            }
        }
        return self._apply_cors(web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(info, indent=2)
        ))

    async def _route_emoji(self, request):
        param = unquote(request.match_info.get("filename", "")).strip()
        file_path = self._resolve_emoji_file_path(param)
        if not file_path:
            file_path = self._resolve_emoji_file_path_by_id(param)
        if not file_path:
            return self._apply_cors(web.Response(status=404, text="Emoji not found"))
        return self._apply_cors(web.FileResponse(file_path, headers={
            "Cache-Control": "public, max-age=3600",
            **self._cors_headers()
        }))

    async def _route_server_asset(self, request):
        asset_name = request.match_info.get("name", "").strip("/")
        file_path = self.server_asset_files.get(asset_name)
        if not file_path or not os.path.isfile(file_path):
            return self._apply_cors(web.Response(status=404, text="Server asset not found"))
        return self._apply_cors(web.FileResponse(file_path, headers={
            "Cache-Control": "public, max-age=3600",
            **self._cors_headers()
        }))

    async def _route_attachment(self, request):
        attachment_id = request.match_info.get("attachment_id", "").strip()

        if not attachment_id:
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "Attachment ID required"})
            ))

        attachment_config = self.config.get("attachments", {})
        if not attachment_config.get("enabled", True):
            return self._apply_cors(web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"error": "Attachments are disabled"})
            ))

        attachment = attachments_db.get_attachment(attachment_id)
        if not attachment:
            return self._apply_cors(web.Response(
                status=404,
                content_type="application/json",
                text=json.dumps({"error": "Attachment not found or expired"})
            ))

        file_path = attachments_db.get_attachment_file_path(attachment_id)
        if not file_path or not os.path.isfile(file_path):
            return self._apply_cors(web.Response(
                status=404,
                content_type="application/json",
                text=json.dumps({"error": "Attachment file not found"})
            ))

        mime_type = attachment.get("mime_type", "application/octet-stream")

        return self._apply_cors(web.FileResponse(
            file_path,
            headers={
                "Content-Type": mime_type,
                "Cache-Control": "public, max-age=3600",
                **self._cors_headers()
            }
        ))

    async def _route_attachment_upload(self, request):
        content_type_header = request.headers.get("Content-Type", "")
        if not content_type_header.startswith("application/json"):
            return self._apply_cors(web.Response(
                status=415,
                content_type="application/json",
                text=json.dumps({"error": "Content-Type must be application/json"})
            ))

        attachment_config = self.config.get("attachments", {})
        if not attachment_config.get("enabled", True):
            return self._apply_cors(web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"error": "Attachments are disabled"})
            ))

        try:
            body = await request.read()
        except Exception:
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "Failed to read request body"})
            ))

        max_size = attachment_config.get("max_size", 104857600)
        if len(body) > max_size:
            return self._apply_cors(web.Response(
                status=413,
                content_type="application/json",
                text=json.dumps({"error": f"Request body too large (max {max_size} bytes)"})
            ))

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "Invalid JSON body"})
            ))

        validator_key = data.get("validator_key")
        validator = data.get("validator")

        if not validator_key or not validator:
            return self._apply_cors(web.Response(
                status=401,
                content_type="application/json",
                text=json.dumps({"error": "validator_key and validator are required for authentication"})
            ))

        import requests
        from db import users as users_db, channels as channels_db, attachments as attachments_db
        from handlers.rotur_api import has_permanent_upload

        try:
            auth_response = requests.get(
                "https://api.rotur.dev/validate",
                params={"key": validator_key, "v": validator},
                timeout=10
            )
        except requests.RequestException:
            return self._apply_cors(web.Response(
                status=502,
                content_type="application/json",
                text=json.dumps({"error": "Failed to validate credentials"})
            ))

        if auth_response.status_code != 200 or auth_response.json().get("valid") != True:
            return self._apply_cors(web.Response(
                status=401,
                content_type="application/json",
                text=json.dumps({"error": "Invalid credentials"})
            ))

        auth_data = auth_response.json()
        user_id = auth_data.get("id", "")
        username = auth_data.get("username", "")

        if not user_id:
            return self._apply_cors(web.Response(
                status=401,
                content_type="application/json",
                text=json.dumps({"error": "User ID not found in authentication response"})
            ))

        user_data = users_db.get_user(user_id)
        if not user_data:
            return self._apply_cors(web.Response(
                status=401,
                content_type="application/json",
                text=json.dumps({"error": "User not found"})
            ))

        user_roles = user_data.get("roles", [])

        file_data = data.get("file")
        name = data.get("name")
        mime_type = data.get("mime_type")
        channel = data.get("channel")
        expires_in_days = data.get("expires_in_days")

        if not file_data or not name or not mime_type or not channel:
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "Missing required fields: file, name, mime_type, channel"})
            ))

        if not channels_db.channel_exists(channel):
            return self._apply_cors(web.Response(
                status=404,
                content_type="application/json",
                text=json.dumps({"error": "Channel does not exist"})
            ))

        if not channels_db.does_user_have_permission(channel, user_roles, "send"):
            return self._apply_cors(web.Response(
                status=403,
                content_type="application/json",
                text=json.dumps({"error": "You don't have permission to send in this channel"})
            ))

        is_permanent = has_permanent_upload(username)

        base_url = ""
        if "server" in self.config and "url" in self.config["server"]:
            base_url = self.config["server"]["url"].rstrip("/")

        attachment = attachments_db.save_attachment(
            file_data=file_data,
            original_name=name,
            mime_type=mime_type,
            uploader_id=user_id,
            uploader_name=username,
            channel=channel,
            permanent=is_permanent,
            custom_expires_in_days=expires_in_days,
        )

        if not attachment:
            return self._apply_cors(web.Response(
                status=500,
                content_type="application/json",
                text=json.dumps({"error": "Failed to save attachment"})
            ))

        attachment_info = attachments_db.get_attachment_info_for_client(attachment, base_url)

        Logger.success(f"Attachment uploaded via HTTP: {attachment['id']} by {username}")

        return self._apply_cors(web.Response(
            status=201,
            content_type="application/json",
            text=json.dumps({
                "attachment": attachment_info,
                "permanent": is_permanent
            })
        ))

    async def _route_webhook(self, request):
        token = request.rel_url.query.get("token")
        if not token:
            return self._apply_cors(web.Response(
                status=401,
                content_type="application/json",
                text=json.dumps({"error": "Webhook token required"})
            ))

        content_type_header = request.headers.get("Content-Type", "")
        if not content_type_header.startswith("application/json"):
            return self._apply_cors(web.Response(
                status=415,
                content_type="application/json",
                text=json.dumps({"error": "Content-Type must be application/json"})
            ))

        try:
            body = await request.read()
        except Exception:
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "Failed to read request body"})
            ))

        if len(body) > 10 * 1024 * 1024:
            return self._apply_cors(web.Response(
                status=413,
                content_type="application/json",
                text=json.dumps({"error": "Request body too large (max 10MB)"})
            ))

        webhook = webhooks_db.get_webhook_by_token(token)
        if not webhook:
            return self._apply_cors(web.Response(
                status=401,
                content_type="application/json",
                text=json.dumps({"error": "Invalid webhook token"})
            ))

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "Invalid JSON body"})
            ))

        channel_name = webhook.get("channel") or ""
        if not channels.channel_exists(channel_name):
            return self._apply_cors(web.Response(
                status=404,
                content_type="application/json",
                text=json.dumps({"error": "Channel not found"})
            ))

        github_event = request.headers.get("X-GitHub-Event", "")
        if github_event and "repository" in data and "ref" in data:
            msg_for_client, error = await github_webhook.handle_github_webhook(data, github_event, channel_name)
            if error:
                return self._apply_cors(web.Response(
                    status=400,
                    content_type="application/json",
                    text=json.dumps({"error": error})
                ))

            if msg_for_client:
                await broadcast_to_channel_except(self.connected_clients, {
                    "cmd": "message_new",
                    "message": msg_for_client,
                    "channel": channel_name,
                    "global": True
                }, channel_name, None)

            Logger.info(f"[GitHub Webhook] {github_event} event received for channel {channel_name}")
            return self._apply_cors(web.Response(status=204))

        content = data.get("content") or data.get("text") or ""
        username = data.get("username") or webhook.get("name") or "Webhook"
        avatar_url = data.get("avatar_url") or webhook.get("avatar")
        embeds = data.get("embeds", [])

        if not content and not embeds:
            content = data.get("message", "")

        if not content and not embeds:
            return self._apply_cors(web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"error": "No content provided"})
            ))

        message_id = str(uuid.uuid4())
        out_msg = {
            "user": "originChats",
            "content": content,
            "timestamp": time.time(),
            "id": message_id,
            "webhook": {
                "id": webhook.get("id"),
                "name": username,
                "avatar": avatar_url
            }
        }

        if embeds:
            out_msg["embeds"] = embeds

        channels.save_channel_message(channel_name, out_msg)

        out_msg_for_client = channels.convert_messages_to_user_format([out_msg])[0]

        await broadcast_to_channel_except(self.connected_clients, {
            "cmd": "message_new",
            "message": out_msg_for_client,
            "channel": channel_name,
            "global": True
        }, channel_name, None)

        return self._apply_cors(web.Response(status=204))

    async def _route_websocket(self, request):
        ws = web.WebSocketResponse(heartbeat=None)
        await ws.prepare(request)

        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For")
            or request.remote
        )
        Logger.add(f"New connection from {client_ip}")

        self.connected_clients.add(ws)
        ws_id = id(ws)
        self._ws_data[ws_id] = {"request": request}
        Logger.info(f"Total connected clients: {len(self.connected_clients)}")

        heartbeat_task = asyncio.create_task(heartbeat(ws, self.heartbeat_interval))

        try:
            connection_validator_key = "originChats-" + secrets.token_urlsafe(24)
            self._ws_data[ws_id]["validator_key"] = connection_validator_key

            attachment_config = self.config.get("attachments", {})
            attachments_info = {
                "enabled": attachment_config.get("enabled", True),
                "max_size": attachment_config.get("max_size", 104857600),
                "allowed_types": attachment_config.get("allowed_types", ["image/*", "video/*", "audio/*", "application/pdf"]),
                "max_attachments_per_user": attachment_config.get("max_attachments_per_user", -1),
                "permanent_tiers": attachment_config.get("permanent_tiers", ["pro", "max"]),
            }

            await send_to_client(ws, {
                "cmd": "handshake",
                "val": {
                    "server": self.config["server"],
                    "limits": self.config["limits"],
                    "attachments": attachments_info,
                    "version": "1.1.0",
                    "validator_key": connection_validator_key,
                    "capabilities": self.capabilities,
                    "permissions": list(permissions_db.PERMISSIONS.keys()),
                    "auth_mode": self.config.get("auth_mode", "rotur")
                }
            })

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        ws_data = self._ws_data.get(ws_id, {})

                        if data.get("cmd") == "auth" and not ws_data.get("authenticated", False):
                            auth_mode = self.config.get("auth_mode", "rotur")
                            if auth_mode == "cracked-only":
                                await send_to_client(ws, {"cmd": "auth_error", "val": "Rotur authentication is disabled. Use login or register commands."})
                                continue
                            
                            auth_server_data = {
                                "connected_clients": self.connected_clients,
                                "connected_usernames": self.connected_usernames,
                                "config": self.config,
                                "plugin_manager": self.plugin_manager,
                                "rate_limiter": self.rate_limiter,
                                "_ws_data": self._ws_data
                            }
                            await handle_authentication(
                                ws, data, self.config, self.connected_clients, client_ip, auth_server_data,
                                validator_key=ws_data.get("validator_key")
                            )
                            continue

                        auth_mode = self.config.get("auth_mode", "rotur")
                        if auth_mode in ("cracked", "cracked-only") and not ws_data.get("authenticated", False):
                            auth_server_data = {
                                "connected_clients": self.connected_clients,
                                "connected_usernames": self.connected_usernames,
                                "config": self.config,
                                "plugin_manager": self.plugin_manager,
                                "rate_limiter": self.rate_limiter,
                                "_ws_data": self._ws_data
                            }
                            if data.get("cmd") == "login":
                                await handle_cracked_auth(ws, data, self.config, self.connected_clients, client_ip, auth_server_data)
                                continue
                            elif data.get("cmd") == "register":
                                await handle_cracked_register(ws, data, self.config, self.connected_clients, client_ip, auth_server_data)
                                continue

                        if not ws_data.get("authenticated", False):
                            await send_to_client(ws, {"cmd": "auth_error", "val": "Authentication required"})
                            continue

                        server_data = {
                            "connected_clients": self.connected_clients,
                            "connected_usernames": self.connected_usernames,
                            "config": self.config,
                            "plugin_manager": self.plugin_manager,
                            "rate_limiter": self.rate_limiter,
                            "send_to_client": send_to_client,
                            "slash_commands": self.slash_commands,
                            "voice_channels": self.voice_channels,
                            "_ws_data": self._ws_data
                        }

                        listener = data.get("listener")
                        if listener and not isinstance(listener, str):
                            Logger.warning(f"Invalid listener type: {type(listener)}")
                            listener = None

                        response = await message_handler.handle(ws, data, server_data)

                        if not response:
                            Logger.warning(f"No response for message: {data}")
                            continue

                        if response.get("global", False):
                            if response.get("channel"):
                                await broadcast_to_channel_except(self.connected_clients, response, response["channel"], ws)
                            else:
                                await broadcast_to_all_except(self.connected_clients, response, ws)
                            if listener:
                                response["listener"] = listener
                            await send_to_client(ws, response)
                            continue

                        if response:
                            if listener:
                                response["listener"] = listener
                            await send_to_client(ws, response)

                    except json.JSONDecodeError:
                        Logger.error(f"Received invalid JSON: {msg.data[:50]}...")
                    except Exception as e:
                        Logger.error(f"Error processing message: {str(e)}")

                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break

        except Exception as e:
            Logger.error(f"Error handling connection: {str(e)}")
        finally:
            heartbeat_task.cancel()
            if ws in self.connected_clients:
                self.connected_clients.remove(ws)
            if ws_id in self._ws_data:
                ws_data = self._ws_data.pop(ws_id, {})
            else:
                ws_data = {}
            Logger.delete(f"Client {client_ip} removed. {len(self.connected_clients)} clients remaining")

            username = ws_data.get("username", "")

            if ws_data.get("authenticated", False):
                user_id = ws_data.get("user_id")
                current_voice_channel = ws_data.get("voice_channel")

                if user_id and current_voice_channel:
                    if current_voice_channel in self.voice_channels and user_id in self.voice_channels[current_voice_channel]:
                        msg_out = {"cmd": "voice_user_left", "channel": current_voice_channel, "username": username}
                        await broadcast_to_voice_channel_with_viewers(
                            self.connected_clients,
                            self.voice_channels,
                            msg_out,
                            msg_out,
                            current_voice_channel,
                            {"_ws_data": self._ws_data}
                        )
                        del self.voice_channels[current_voice_channel][user_id]
                        if not self.voice_channels[current_voice_channel]:
                            del self.voice_channels[current_voice_channel]

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
                        }, {"_ws_data": self._ws_data})
                        Logger.success(f"Broadcast user_disconnect: {username}")
                    else:
                        Logger.info(f"User {username} still has {self.connected_usernames[username]} active connection(s)")

        return ws

    async def broadcast_wrapper(self, message):
        """Wrapper for broadcast_to_all to maintain compatibility with watchers"""
        await broadcast_to_all(self.connected_clients, message)
    
    async def start_server(self):
        """Start the WebSocket server"""
        # Store the main event loop for use in other threads
        self.main_event_loop = asyncio.get_event_loop()
        self.file_observer = watchers.setup_file_watchers(
            self.broadcast_wrapper, self.main_event_loop, lambda: self.connected_clients, lambda: {
                "connected_clients": self.connected_clients,
                "config": self.config,
                "plugin_manager": self.plugin_manager,
                "rate_limiter": self.rate_limiter,
                "slash_commands": self.slash_commands,
                "voice_channels": self.voice_channels,
                "_ws_data": self._ws_data,
                "send_to_client": send_to_client
            }
        )

        port = self.config.get("websocket", {}).get("port", 5613)
        host = self.config.get("websocket", {}).get("host", "127.0.0.1")

        Logger.info(f"Starting server on {host}:{port}")

        server_data = {
            "connected_clients": self.connected_clients,
            "config": self.config,
            "plugin_manager": self.plugin_manager,
            "rate_limiter": self.rate_limiter
        }
        self.plugin_manager.trigger_event("server_start", None, {}, server_data)

        # Start the daily cleanup task
        self._cleanup_task = asyncio.create_task(self._daily_cleanup_task())

        max_upload_size = self.config.get("attachments", {}).get("max_size", 100 * 1024 * 1024)
        app = web.Application(client_max_size=max_upload_size)

        # OPTIONS preflight for all routes
        app.router.add_route("OPTIONS", "/{path_info:.*}", self._route_options)

        # WebSocket on root path only
        app.router.add_get("/", self._route_websocket)

        # HTTP routes
        app.router.add_get("/index.html", self._route_index)
        app.router.add_get("/info", self._route_info)
        app.router.add_get("/emojis/{filename}", self._route_emoji)
        app.router.add_get("/server-assets/{name}", self._route_server_asset)
        app.router.add_get("/attachments/{attachment_id}", self._route_attachment)
        app.router.add_post("/attachments/upload", self._route_attachment_upload)

        # Webhook (POST)
        app.router.add_post("/webhooks", self._route_webhook)
        app.router.add_post("/webhooks/{path_info:.*}", self._route_webhook)

        # 404 handler for unknown HTTP routes
        app.router.add_get("/{path_info:.*}", self._route_404)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        Logger.success(f"Server running at ws://{host}:{port}")

        try:
            await asyncio.Future()  # run forever
        finally:
            self._cleanup_task.cancel()
            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join()
            Logger.info("File watcher stopped")
            await runner.cleanup()

    async def _daily_cleanup_task(self):
        """Run attachment cleanup once every 24 hours."""
        while True:
            try:
                await asyncio.sleep(24 * 60 * 60)  # 24 hours
                result = attachments_db.run_daily_cleanup()
                if result["total"] > 0:
                    Logger.info(f"Daily cleanup: removed {result['total']} attachments")
            except asyncio.CancelledError:
                break
            except Exception as e:
                Logger.error(f"Error in daily cleanup task: {e}")