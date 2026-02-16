# OriginChats Documentation

Welcome to the OriginChats server documentation. OriginChats is a WebSocket-based real-time chat server with voice channels, slash commands, plugins, and role-based permissions.

> **Client List:** See [clients.md](../clients.md) for a list of official and community clients.

---

## Table of Contents

- [Getting Started](#getting-started)
  - [Quick Start](#quick-start)
  - [Setup](#setup)
  - [Configuration](#configuration)
- [API Reference](#api-reference)
- [Commands](#commands)
- [Data Structures](#data-structures)
- [Client Development](#client-development)

---

## Getting Started

### Quick Start

OriginChats is a real-time WebSocket chat server built in Python. It supports text and voice channels, role-based permissions, slash commands, and plugin extensibility.

### Setup

1. **Requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration:**
   - Edit `config.json` for server settings
   - Configure Rotur authentication service

3. **Start the Server:**
   ```bash
   python init.py
   ```

### Configuration

Key configuration options in `config.json`:

```json
{
  "websocket": {
    "host": "127.0.0.1",
    "port": 5613
  },
  "rotur": {
    "validate_url": "...",
    "validate_key": "..."
  },
  "rate_limiting": {
    "enabled": true,
    "messages_per_minute": 30
  },
  "limits": {
    "post_content": 2000
  }
}
```

For full configuration details, see [Data Structures: Config](data/config.md).

---

## API Reference

- [Protocol Documentation](protocol.md) - WebSocket protocol details, handshake, heartbeat
- [Authentication](auth.md) - User authentication flow with Rotur service
- [Error Handling](errors.md) - Common error responses and their meanings

---

## Commands

### Text Messaging

| Command | Description | Documentation |
|---------|-------------|---------------|
| `message_new` | Send a new message | [View](commands/message_new.md) |
| `message_edit` | Edit an existing message | [View](commands/message_edit.md) |
| `message_delete` | Delete a message | [View](commands/message_delete.md) |
| `typing` | Send typing indicator | [View](commands/typing.md) |
| `messages_get` | Get channel messages | [View](commands/messages_get.md) |
| `message_get` | Get a specific message | [View](commands/message_get.md) |
| `message_replies` | Get replies to a message | [View](commands/message_replies.md) |
| `messages_search` | Search messages in a channel | [View](commands/messages_search.md) |
| `messages_pinned` | Get pinned messages | [View](commands/messages_pinned.md) |
| `message_react_add` | Add reaction to message | [View](commands/message_react_add.md) |
| `message_react_remove` | Remove reaction from message | [View](commands/message_react_remove.md) |
| `message_pin` / `message_unpin` | Pin/unpin a message | [View](commands/message_pin.md) |

### Voice Channels

| Command | Description | Documentation |
|---------|-------------|---------------|
| `voice_join` | Join a voice channel | [View](commands/voice_join.md) |
| `voice_leave` | Leave current voice channel | [View](commands/voice_leave.md) |
| `voice_mute` / `voice_unmute` | Mute/unmute microphone | [View](commands/voice_mute.md) |
| `voice_state` | Get voice channel participants | [View](commands/voice_state.md) |

### User Management

| Command | Description | Documentation |
|---------|-------------|---------------|
| `users_list` | List all users | [View](commands/users_list.md) |
| `users_online` | List online users | [View](commands/users_online.md) |
| `users_banned_list` | List banned users (owner only) | [View](commands/users_banned_list.md) |
| `user_ban` | Ban a user (owner only) | [View](commands/user_ban.md) |
| `user_unban` | Unban a user (owner only) | [View](commands/user_unban.md) |
| `user_timeout` | Set user timeout (owner only) | [View](commands/user_timeout.md) |
| `user_leave` | Disconnect a user (owner only) | [View](commands/user_leave.md) |
| `user_roles_add` | Add roles to a user (owner only) | [View](commands/user_roles_add.md) |
| `user_roles_remove` | Remove roles from a user (owner only) | [View](commands/user_roles_remove.md) |
| `user_roles_get` | Get a user's roles (owner only) | [View](commands/user_roles_get.md) |

### Role Management

| Command | Description | Documentation |
|---------|-------------|---------------|
| `role_create` | Create a new role (owner only) | [View](commands/role_create.md) |
| `role_update` | Update a role (owner only) | [View](commands/role_update.md) |
| `role_delete` | Delete a role (owner only) | [View](commands/role_delete.md) |
| `roles_list` | List all roles (owner only) | [View](commands/roles_list.md) |

### Channel Management

| Command | Description | Documentation |
|---------|-------------|---------------|
| `channels_get` | Get available channels | [View](commands/channels_get.md) |
| `channel_create` | Create a new channel (owner only) | [View](commands/channel_create.md) |
| `channel_update` | Update a channel (owner only) | [View](commands/channel_update.md) |
| `channel_move` | Move a channel to new position (owner only) | [View](commands/channel_move.md) |
| `channel_delete` | Delete a channel (owner only) | [View](commands/channel_delete.md) |

### Server Management

| Command | Description | Documentation |
|---------|-------------|---------------|
| `ping` | Ping the server | [View](commands/ping.md) |
| `plugins_list` | List loaded plugins | [View](commands/plugins_list.md) |
| `plugins_reload` | Reload plugins | [View](commands/plugins_reload.md) |
| `rate_limit_status` | Check rate limit status | [View](commands/rate_limit_status.md) |
| `rate_limit_reset` | Reset rate limit (owner only) | [View](commands/rate_limit_reset.md) |

### Slash Commands

| Command | Description | Documentation |
|---------|-------------|---------------|
| `slash_register` | Register a new slash command (owner only) | [View](commands/slash_register.md) |
| `slash_list` | List all registered slash commands | [View](commands/slash_list.md) |
| `slash_call` | Execute a slash command | [View](commands/slash_call.md) |

---

## Data Structures

- [User Object](data/user.md) - User data structure
- [Channel Object](data/channels.md) - Channel configuration, permissions, and voice state
- [Message Object](data/messages.md) - Message structure with replies and reactions
- [Role Object](data/roles.md) - Role definitions and colors
- [Config Schema](data/config.md) - Server configuration options
- [Permissions System](data/permissions.md) - How role-based permissions work

---

## Client Development

For developers building clients:

1. **Connection Flow:**
   - Connect to WebSocket server
   - Receive handshake packet
   - Authenticate using Rotur validator
   - Start sending/receiving commands

2. **Voice Channels:**
   - WebRTC peer connection setup
   - Join/leave voice channels
   - Mute/unmute functionality

3. **Commands Overview:**
   - All commands use JSON format with `cmd` field
   - Global broadcasts use `global: true` flag
   - Errors return `{ "cmd": "error", "val": "message" }`

---

## Rate Limiting

OriginChats includes built-in rate limiting:

- **Per-minute limit:** Maximum messages per user per minute (configurable)
- **Burst protection:** Prevents spam in short time windows
- **Cooldown:** Temporary restriction after burst limit exceeded

Response format:
```json
{
  "cmd": "rate_limit",
  "length": <milliseconds>
}
```

See [README.md](../README.md) for server architecture and rate limiting details.

---

## Support

For issues, questions, or contributions:
- **Source Code:** [Repository](https://github.com/...)
- **Issue Tracker:** Open an issue on GitHub
- **Protocol:** See [protocol.md](protocol.md)

---

**Last Updated:** 2025-02-16
