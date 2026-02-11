# Discord Bridge Plugin for OriginChats
# Direct Discord Gateway connection and API integration
# Syncs channels and bridges messages between OriginChats and Discord

import os
import json
import time
import uuid
import asyncio
import aiohttp
import websocket
import websockets
import hashlib
from typing import Dict, List, Optional
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger

# Try to import dotenv, handle gracefully if not available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), 'discordBridge.env'))
except ImportError:
    Logger.warning("python-dotenv not available, reading environment directly")

from db import channels, users

# Configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID')
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
ROTUR_API_BASE = "https://social.rotur.dev"
WEBHOOK_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'discord_webhooks.json')
SEND_PERMISSION_WARNINGS = os.getenv('DISCORD_SEND_PERMISSION_WARNINGS', 'true').lower() == 'true'

# Global variables
discord_gateway = None
user_cache = {}
server_data_global = None
guild_id = None
last_channels_hash = None
discord_message_map = {}  # Maps Discord message IDs to OriginChats message IDs

class DiscordGateway:
    """Direct Discord Gateway connection"""
    
    def __init__(self, token):
        self.token = token
        self.session_id = None
        self.sequence = None
        self.heartbeat_interval = 0
        self.websocket = None
        self.heartbeat_task = None
        self.running = False
        
    async def connect(self):
        """Connect to Discord Gateway"""
        try:
            Logger.info("Connecting to Discord Gateway...")
            self.websocket = await websockets.connect(DISCORD_GATEWAY_URL)
            self.running = True
            
            # Start message handler
            asyncio.create_task(self.handle_messages())
            
            Logger.success("Connected to Discord Gateway")
            
        except Exception as e:
            Logger.error(f"Failed to connect to Discord Gateway: {e}")
            
    async def handle_messages(self):
        """Handle incoming Gateway messages"""
        try:
            if not self.websocket or not self.running:
                return
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.process_gateway_event(data)
                except Exception as e:
                    Logger.error(f"Error processing Gateway message: {e}")
        except websockets.exceptions.ConnectionClosed:
            Logger.warning("Discord Gateway connection closed")
            self.running = False
        except Exception as e:
            Logger.error(f"Gateway message handler error: {e}")
                
    async def process_gateway_event(self, data):
        """Process Discord Gateway events"""
        op = data.get('op')
        t = data.get('t')
        d = data.get('d')
        s = data.get('s')
        
        if s:
            self.sequence = s
            
        if op == 10:  # Hello
            self.heartbeat_interval = d['heartbeat_interval']
            await self.identify()
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            
        elif op == 0:  # Dispatch
            if t == 'READY':
                self.session_id = d['session_id']
                Logger.success(f"Discord bot ready: {d['user']['username']}#{d['user']['discriminator']}")
                await self.setup_guild_channels()
                
            elif t == 'MESSAGE_CREATE':
                await self.handle_discord_message(d)
                
            elif t == 'MESSAGE_UPDATE':
                await self.handle_discord_message_edit(d)
                
            elif t == 'MESSAGE_DELETE':
                await self.handle_discord_message_delete(d)
                
        elif op == 1:  # Heartbeat request
            await self.send_heartbeat()
            
        elif op == 11:  # Heartbeat ACK
            pass  # Heartbeat acknowledged
            
    async def identify(self):
        if self.websocket is None or not self.running:
            return
        """Send IDENTIFY payload"""
        identify_payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "intents": 4194303,  # GUILDS (1) + GUILD_MESSAGES (512)
                "properties": {
                    "os": "originchats",
                    "browser": "originchats",
                    "device": "originchats"
                }
            }
        }
        await self.websocket.send(json.dumps(identify_payload))
        
    async def send_heartbeat(self):
        if self.websocket is None or not self.running:
            return
        """Send heartbeat to maintain connection"""
        heartbeat_payload = {
            "op": 1,
            "d": self.sequence
        }
        await self.websocket.send(json.dumps(heartbeat_payload))
        
    async def heartbeat_loop(self):
        """Heartbeat loop"""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval / 1000)
                if self.running:
                    await self.send_heartbeat()
            except Exception as e:
                Logger.error(f"Heartbeat error: {e}")
                break
            
    async def setup_guild_channels(self):
        """Setup channels for the specified guild"""
        global guild_id
        
        if not DISCORD_GUILD_ID:
            Logger.error("DISCORD_GUILD_ID not set in environment")
            Logger.info("Please set DISCORD_GUILD_ID in plugins/discordBridge.env")
            return
            
        guild_id = DISCORD_GUILD_ID
        Logger.info(f"Setting up channels for guild: {guild_id}")
        
        # Get guild channels
        channels_data = await self.api_request('GET', f'/guilds/{guild_id}/channels')
        if not channels_data:
            Logger.error(f"Failed to get channels for guild {guild_id}. Check bot permissions and guild ID.")
            return
            
        # Create missing channels and webhooks
        await self.sync_channels_with_origin(channels_data)
        
        # Start periodic channel sync checker
        asyncio.create_task(self.periodic_channel_sync())
        
    def normalize_discord_channel_name(self, name):
        """Normalize channel name to match Discord's format"""
        return name.lower().replace(' ', '-').replace('_', '-')
    
    async def sync_channels_with_origin(self, discord_channels):
        """Sync Discord channels with OriginChats channels"""
        origin_channels = load_origin_channels()
        
        # Filter origin channels to only include those visible to users
        visible_origin_channels = []
        position = 0
        
        for origin_channel in origin_channels:
            if origin_channel.get('type') != 'text':
                continue
                
            # Check if channel is visible to users with "user" permission
            permissions = origin_channel.get('permissions', {})
            view_permissions = permissions.get('view', [])
            
            if 'user' in view_permissions:
                channel_data = origin_channel.copy()
                channel_data['expected_position'] = position
                visible_origin_channels.append(channel_data)
                position += 1
        
        Logger.info(f"Found {len(visible_origin_channels)} channels visible to users")
        
        # Create a map of existing Discord channels using normalized names
        discord_channel_map = {}
        for ch in discord_channels:
            if ch['type'] == 0:  # Text channels
                discord_channel_map[ch['name']] = ch
        
        Logger.info(f"Existing Discord channels: {list(discord_channel_map.keys())}")
        
        # First pass: Create missing channels
        for origin_channel in visible_origin_channels:
            channel_name = origin_channel['name']
            normalized_name = self.normalize_discord_channel_name(channel_name)
            
            Logger.info(f"Checking channel '{channel_name}' -> normalized: '{normalized_name}'")
            
            # Check if channel exists (compare normalized names)
            if normalized_name not in discord_channel_map:
                # Create channel
                Logger.info(f"Creating Discord channel: #{channel_name} (normalized: {normalized_name})")
                channel_data = await self.create_guild_channel(
                    channel_name, 
                    origin_channel.get('description', ''),
                    origin_channel['expected_position']
                )
                if channel_data:
                    discord_channel_map[normalized_name] = channel_data
            else:
                Logger.info(f"Channel '{channel_name}' already exists as '{normalized_name}'")
        
        # Second pass: Update positions and setup webhooks
        for origin_channel in visible_origin_channels:
            channel_name = origin_channel['name']
            normalized_name = self.normalize_discord_channel_name(channel_name)
            
            if normalized_name in discord_channel_map:
                discord_channel = discord_channel_map[normalized_name]
                expected_position = origin_channel['expected_position']
                
                # Check if position needs updating
                if discord_channel.get('position', 0) != expected_position:
                    Logger.info(f"Updating position for #{channel_name}: {discord_channel.get('position', 0)} → {expected_position}")
                    await self.update_channel_position(discord_channel['id'], expected_position)
                
                # Setup webhook for this channel
                await self.setup_webhook(discord_channel, channel_name)
                
    async def create_guild_channel(self, name, description="", position=None):
        """Create a text channel in the guild"""
        payload = {
            "name": name,
            "type": 0,  # Text channel
            "topic": description
        }
        if position is not None:
            payload["position"] = position
        
        return await self.api_request('POST', f'/guilds/{guild_id}/channels', payload)
    
    async def update_channel_position(self, channel_id, position):
        """Update a channel's position"""
        payload = {"position": position}
        return await self.api_request('PATCH', f'/channels/{channel_id}', payload)
        
    async def setup_webhook(self, channel, origin_channel_name):
        """Setup webhook for a channel"""
        # Get existing webhooks
        webhooks = await self.api_request('GET', f'/channels/{channel["id"]}/webhooks')
        if webhooks is None or not isinstance(webhooks, list):
            return
            
        # Look for existing OriginChats webhook
        origin_webhook = None
        for webhook in webhooks:
            if isinstance(webhook, dict) and webhook.get('name') == f"OriginChats-{origin_channel_name}":
                origin_webhook = webhook
                break
                
        # Create webhook if it doesn't exist
        if not origin_webhook:
            Logger.info(f"Creating webhook for #{origin_channel_name}")
            webhook_payload = {
                "name": f"OriginChats-{origin_channel_name}"
            }
            origin_webhook = await self.api_request('POST', f'/channels/{channel["id"]}/webhooks', webhook_payload)
            
        if origin_webhook and isinstance(origin_webhook, dict):
            # Save webhook URL to config
            webhook_url = f"https://discord.com/api/webhooks/{origin_webhook.get('id')}/{origin_webhook.get('token')}"
            save_webhook_config(origin_channel_name, webhook_url)
            Logger.success(f"Webhook configured for #{origin_channel_name}")
            
    async def handle_discord_message(self, message_data):
        """Handle incoming Discord message"""
        # Skip bot messages
        if message_data.get('author', {}).get('bot', False):
            return

        # Get channel info
        channel_id = message_data['channel_id']
        content = message_data.get('content', '')
        author = message_data['author']
        message_id = message_data.get('id')
    
        # Skip empty messages
        if not content or content.strip() == '' or message_data.get('guild_id') != guild_id:
            return
        
        # Get channel name
        channel_info = await self.api_request('GET', f'/channels/{channel_id}')
        if not channel_info or not isinstance(channel_info, dict):
            return
            
        channel_name = channel_info.get('name')
        if not channel_name:
            return
        
        # Get Rotur username
        discord_user_id = author['id']
        rotur_username = await get_rotur_username(discord_user_id)
        if not rotur_username:
            rotur_username = getattr(websocket, "username", "")
        else:
            rotur_username = rotur_username.lower()
        
        # Check if user has permission to send messages in this channel
        if not await self.check_send_permission(rotur_username, channel_name):
            Logger.warning(f"User {rotur_username} doesn't have permission to send messages in #{channel_name}")
            # Delete the message in Discord
            deleted = await self.delete_discord_message(channel_id, message_id)
            if deleted and SEND_PERMISSION_WARNINGS:
                # Optionally, send a DM to the user explaining why their message was deleted
                await self.send_permission_warning(discord_user_id, channel_name)
            return
            
        # Create OriginChats message
        out_msg = {
            "user": rotur_username,
            "content": content,
            "timestamp": time.time(),
            "type": "message",
            "pinned": False,
            "id": str(uuid.uuid4()),
            "source": "discord",
            "discord_user_id": discord_user_id,
            "discord_username": author['username'],
            "discord_message_id": message_id  # Store Discord message ID for edits/deletes
        }
        
        # Store mapping for edits and deletes
        discord_message_map[message_id] = out_msg["id"]
        
        # Clean up old mappings periodically (keep only last 1000 messages)
        if len(discord_message_map) > 1000:
            # Remove oldest 200 entries
            oldest_keys = list(discord_message_map.keys())[:200]
            for key in oldest_keys:
                del discord_message_map[key]
        
        # Save to OriginChats
        channels.save_channel_message(channel_name, out_msg)
        
        # Broadcast to OriginChats clients
        if server_data_global and "connected_clients" in server_data_global:
            from handlers.websocket_utils import broadcast_to_channel
            broadcast_message = {
                "cmd": "message_new",
                "channel": channel_name,
                "message": out_msg
            }
            await broadcast_to_channel(
                server_data_global["connected_clients"], 
                broadcast_message,
                channel_name
            )
            
        Logger.discordupdate(f"Forwarded Discord message from {rotur_username} to #{channel_name}: '{content}'")
        
    async def api_request(self, method, endpoint, data=None):
        """Make Discord API request"""
        headers = {
            'Authorization': f'Bot {self.token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{DISCORD_API_BASE}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                if method == 'GET':
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            Logger.error(f"API request failed: {response.status} {await response.text()}")
                            return None
                elif method == 'POST':
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status in [200, 201]:
                            return await response.json()
                        else:
                            Logger.error(f"API request failed: {response.status} {await response.text()}")
                            return None
                elif method == 'PATCH':
                    async with session.patch(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            Logger.error(f"API request failed: {response.status} {await response.text()}")
                            return None
                elif method == 'DELETE':
                    async with session.delete(url, headers=headers) as response:
                        if response.status == 204:
                            return {"success": True}  # DELETE successful, return dict to indicate success
                        else:
                            Logger.error(f"API request failed: {response.status} {await response.text()}")
                            return None
        except Exception as e:
            Logger.error(f"API request error: {e}")
            return None
    
    async def periodic_channel_sync(self):
        """Periodically check for channel changes and resync if needed"""
        global last_channels_hash
        
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if not self.running:
                    break
                
                # Calculate hash of current channels
                current_channels = load_origin_channels()
                visible_channels = []
                
                for channel in current_channels:
                    if channel.get('type') == 'text':
                        permissions = channel.get('permissions', {})
                        view_permissions = permissions.get('view', [])
                        if 'user' in view_permissions:
                            visible_channels.append({
                                'name': channel['name'],
                                'description': channel.get('description', ''),
                                'permissions': channel.get('permissions', {})
                            })
                
                # Create hash of channel structure
                channels_str = json.dumps(visible_channels, sort_keys=True)
                current_hash = hashlib.md5(channels_str.encode()).hexdigest()
                
                # Check if channels changed
                if last_channels_hash is None:
                    last_channels_hash = current_hash
                elif last_channels_hash != current_hash:
                    Logger.info("Channel structure changed, resyncing Discord channels...")
                    last_channels_hash = current_hash
                    
                    # Get current Discord channels and resync
                    channels_data = await self.api_request('GET', f'/guilds/{guild_id}/channels')
                    if channels_data:
                        await self.sync_channels_with_origin(channels_data)
                        
            except Exception as e:
                Logger.error(f"Error in periodic channel sync: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def check_send_permission(self, username, channel_name):
        """Check if a user has permission to send messages in a channel"""
        try:
            # Load channel configuration
            origin_channels = load_origin_channels()
            
            # Find the channel
            channel_config = None
            for channel in origin_channels:
                if channel.get('name') == channel_name and channel.get('type') == 'text':
                    channel_config = channel
                    break
            
            if not channel_config:
                Logger.warning(f"Channel {channel_name} not found in configuration")
                return False
            
            # Get send permissions for the channel
            permissions = channel_config.get('permissions', {})
            send_permissions = permissions.get('send', [])
            
            if not send_permissions:
                return True
            
            # Get user roles
            user_roles = users.get_user_roles(username)
            if not user_roles:
                # Create user with default role if they don't exist
                users.add_user(username)
                user_roles = users.get_user_roles(username)
            
            # Check if user has any of the required roles
            for role in user_roles:
                if role in send_permissions:
                    return True
            
            return False
            
        except Exception as e:
            Logger.error(f"Error checking send permission for {username} in {channel_name}: {e}")
            return False
    
    async def delete_discord_message(self, channel_id, message_id):
        """Delete a message in Discord"""
        try:
            result = await self.api_request('DELETE', f'/channels/{channel_id}/messages/{message_id}')
            if result and result.get('success'):
                Logger.success(f"Deleted unauthorized message {message_id} in Discord channel {channel_id}")
                return True
            else:
                Logger.error(f"Failed to delete message {message_id} in Discord channel {channel_id}")
                return False
        except Exception as e:
            Logger.error(f"Error deleting Discord message {message_id}: {e}")
            return False
    
    async def send_permission_warning(self, discord_user_id, channel_name):
        """Send a DM to user explaining why their message was deleted"""
        try:
            # Create DM channel
            dm_channel = await self.api_request('POST', '/users/@me/channels', {
                'recipient_id': discord_user_id
            })
            
            if dm_channel and isinstance(dm_channel, dict):
                dm_channel_id = dm_channel.get('id')
                if dm_channel_id:
                    # Send warning message
                    warning_message = f"Your message in #{channel_name} was deleted because you don't have permission to send messages in that channel. Please check with server administrators about your role permissions."
                    
                    await self.api_request('POST', f'/channels/{dm_channel_id}/messages', {
                        'content': warning_message
                    })
                    
                    Logger.info(f"Sent permission warning to Discord user {discord_user_id}")
        except Exception as e:
            Logger.error(f"Error sending permission warning to Discord user {discord_user_id}: {e}")

    async def handle_discord_message_edit(self, message_data):
        """Handle Discord message edits"""
        try:
            # Skip bot messages
            if message_data.get('author', {}).get('bot', False):
                return

            # Get channel info
            channel_id = message_data['channel_id']
            content = message_data.get('content', '')
            author = message_data.get('author', {})
            discord_message_id = message_data.get('id')
            
            # Skip if no content or not in our guild
            if not content or content.strip() == '' or message_data.get('guild_id') != guild_id:
                return

            # Get channel name
            channel_info = await self.api_request('GET', f'/channels/{channel_id}')
            if not channel_info or not isinstance(channel_info, dict):
                return
                
            channel_name = channel_info.get('name')
            if not channel_name:
                return

            # Get Rotur username
            discord_user_id = author['id']
            rotur_username = await get_rotur_username(discord_user_id)
            if not rotur_username:
                rotur_username = f"discord-{author['username'].lower()}"
            else:
                rotur_username = rotur_username.lower()

            # Check if user has permission to send messages in this channel
            if not await self.check_send_permission(rotur_username, channel_name):
                Logger.warning(f"User {rotur_username} doesn't have permission to edit messages in #{channel_name}")
                # Delete the edited message
                await self.delete_discord_message(channel_id, discord_message_id)
                return

            # Check if we have this Discord message mapped to an OriginChats message
            if discord_message_id in discord_message_map:
                originchats_message_id = discord_message_map[discord_message_id]
                
                # Get the original message to update it
                original_message = channels.get_channel_message(channel_name, originchats_message_id)
                if original_message:
                    # Update the message content and add edit metadata
                    success = channels.edit_channel_message(channel_name, originchats_message_id, content)
                    
                    if success:
                        # Get the updated message and add edit metadata
                        updated_message = channels.get_channel_message(channel_name, originchats_message_id)
                        if updated_message:
                            # Add edit metadata (we need to manually update since edit_channel_message only updates content)
                            updated_message['edited'] = True
                            updated_message['edited_timestamp'] = time.time()
                            
                            # Broadcast the edit
                            if server_data_global and "connected_clients" in server_data_global:
                                from handlers.websocket_utils import broadcast_to_channel
                                broadcast_message = {
                                    "cmd": "message_edit",
                                    "channel": channel_name,
                                    "message_id": originchats_message_id,
                                    "val": updated_message
                                }
                                await broadcast_to_channel(
                                    server_data_global["connected_clients"],
                                    broadcast_message,
                                    channel_name
                                )
                                
                            Logger.success(f"Updated Discord message edit from {rotur_username} in #{channel_name}")
                    else:
                        Logger.error(f"Failed to edit message {originchats_message_id} in #{channel_name}")
                else:
                    Logger.warning(f"Original message {originchats_message_id} not found in #{channel_name}")
            else:
                Logger.info(f"Discord message {discord_message_id} not found in mapping for edit (possibly from before bot restart)")

        except Exception as e:
            Logger.error(f"Error handling Discord message edit: {e}")

    async def handle_discord_message_delete(self, message_data):
        """Handle Discord message deletions"""
        try:
            channel_id = message_data['channel_id']
            discord_message_id = message_data['id']
            
            # Skip if not in our guild
            if message_data.get('guild_id') != guild_id:
                return

            # Get channel name
            channel_info = await self.api_request('GET', f'/channels/{channel_id}')
            if not channel_info or not isinstance(channel_info, dict):
                return
                
            channel_name = channel_info.get('name')
            if not channel_name:
                return

            # Check if we have this Discord message mapped to an OriginChats message
            if discord_message_id in discord_message_map:
                originchats_message_id = discord_message_map[discord_message_id]
                
                # Delete the message from the database
                success = channels.delete_channel_message(channel_name, originchats_message_id)
                
                if success:
                    # Remove from mapping
                    del discord_message_map[discord_message_id]
                    
                    # Broadcast the deletion
                    if server_data_global and "connected_clients" in server_data_global:
                        from handlers.websocket_utils import broadcast_to_channel
                        broadcast_message = {
                            "cmd": "message_delete",
                            "channel": channel_name,
                            "message_id": originchats_message_id
                        }
                        await broadcast_to_channel(
                            server_data_global["connected_clients"],
                            broadcast_message,
                            channel_name
                        )
                        
                    Logger.success(f"Deleted Discord message {discord_message_id} from #{channel_name}")
                else:
                    Logger.error(f"Failed to delete message {originchats_message_id} from #{channel_name}")
            else:
                Logger.info(f"Discord message {discord_message_id} not found in mapping for deletion (possibly from before bot restart)")

        except Exception as e:
            Logger.error(f"Error handling Discord message delete: {e}")

def load_origin_channels():
    """Load OriginChats channels from channels.json"""
    try:
        channels_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'channels.json')
        with open(channels_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        Logger.error(f"Error loading OriginChats channels: {str(e)}")
        return []

def load_webhook_config():
    """Load webhook configuration from file"""
    try:
        if os.path.exists(WEBHOOK_CONFIG_FILE):
            with open(WEBHOOK_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        Logger.error(f"Error loading webhook config: {str(e)}")
    return {}

def save_webhook_config(channel_name, webhook_url):
    """Save webhook configuration to file"""
    try:
        config = load_webhook_config()
        config[channel_name] = webhook_url
        with open(WEBHOOK_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        Logger.error(f"Error saving webhook config: {str(e)}")

async def get_rotur_username(discord_id):
    """Get Rotur username from Discord ID"""
    try:
        # Check cache first
        if discord_id in user_cache:
            return user_cache[discord_id].lower()
            
        # Make API request
        async with aiohttp.ClientSession() as session:
            url = f"{ROTUR_API_BASE}/profile?discord_id={discord_id}&include_posts=0"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    username = data.get('username')
                    if username:
                        username_lower = username.lower()
                        user_cache[discord_id] = username_lower
                        return username_lower
                        
    except Exception as e:
        Logger.error(f"Error getting Rotur username for Discord ID {discord_id}: {str(e)}")
    
    return None

async def send_to_discord(channel_name, message_data):
    """Send message from OriginChats to Discord via webhook"""
    try:
        # Load webhook config
        webhook_config = load_webhook_config()
        
        if channel_name not in webhook_config:
            # Logger.warning(f"No webhook found for channel: {channel_name}")
            return
            
        webhook_url = webhook_config[channel_name]
        
        # Skip invalid webhook URLs
        if "PASTE_DISCORD_WEBHOOK_URL_HERE" in webhook_url or "EXAMPLE_WEBHOOK_URL_HERE" in webhook_url:
            return
        
        # Prepare webhook payload
        username = message_data.get('user', 'Unknown')
        content = message_data.get('content', '')
        
        # Skip if message came from Discord to avoid loops
        if message_data.get('source') == 'discord':
            return
            
        payload = {
            'username': f"{username}",
            'content': content,
            'avatar_url': f"https://avatars.rotur.dev/{username}"
        }
        
        # Send webhook
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 204:
                    Logger.info(f"Sent message to Discord #{channel_name} from {username}")
                else:
                    Logger.error(f"Failed to send webhook: {response.status}")
                    
    except Exception as e:
        Logger.error(f"Error sending to Discord: {str(e)}")

def getInfo():
    """Get information about the plugin"""
    return {
        "name": "Discord Bridge",
        "description": "Bridges messages between OriginChats and Discord using direct Gateway connection and API",
        "version": "2.0.0",
        "author": "OriginChats",
        "handles": [
            "new_message",
            "server_start"
        ]
    }

async def on_new_message(ws, message_data, server_data=None):
    """Handle new messages from OriginChats"""
    try:
        # Extract message details
        content = message_data.get("content", "")
        channel = message_data.get("channel", "")
        user = message_data.get("user", "")
        message_obj = message_data.get("message", {})
        
        # Debug logging
        Logger.info(f"OriginChats message: user={user}, channel={channel}, content='{content}'")
        Logger.info(f"Message object: {message_obj}")
        
        # Use message_obj if it has content, otherwise use direct content
        if message_obj and message_obj.get('content'):
            final_message = message_obj
        else:
            # Create message object from direct data
            final_message = {
                'user': user.lower() if user else 'unknown',
                'content': content,
                'timestamp': time.time(),
                'type': 'message'
            }
        
        # Ensure username is lowercase
        if 'user' in final_message:
            final_message['user'] = final_message['user'].lower()
        
        # Send to Discord
        await send_to_discord(channel, final_message)
        
    except Exception as e:
        Logger.error(f"Error in Discord bridge new_message handler: {str(e)}")
        import traceback
        traceback.print_exc()

async def on_server_start(ws, message_data, server_data=None):
    """Handle server start event"""
    global discord_gateway, server_data_global
    
    try:
        # Store server data globally
        server_data_global = server_data
        
        # Start Discord Gateway connection
        if not discord_gateway and DISCORD_BOT_TOKEN:
            if not DISCORD_GUILD_ID:
                Logger.error("DISCORD_GUILD_ID not set in environment")
                Logger.info("Please set DISCORD_GUILD_ID in plugins/discordBridge.env")
                return
                
            Logger.info(f"Starting Discord Gateway connection for guild: {DISCORD_GUILD_ID}")
            discord_gateway = DiscordGateway(DISCORD_BOT_TOKEN)
            await discord_gateway.connect()
        elif not DISCORD_BOT_TOKEN:
            Logger.error("Discord bot token not found in environment")
            Logger.info("Please set DISCORD_BOT_TOKEN in plugins/discordBridge.env")
        else:
            Logger.info("Discord Gateway already connected")
            
    except Exception as e:
        Logger.error(f"Error starting Discord bridge: {str(e)}")

# Make sure we export the event handlers
__all__ = ['getInfo', 'on_new_message', 'on_server_start']
