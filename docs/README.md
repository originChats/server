# OriginChats Documentation

Welcome to the OriginChats documentation.

## Quick Links

| Topic | Description |
|-------|-------------|
| [Overview](overview.md) | Core concepts explained simply |
| [Getting Started](getting-started.md) | Connect and use the API |
| [Client Development](clients.md) | Build your own client |
| [Plugin Development](plugins.md) | Create server plugins |
| [Production Setup](production.md) | Deploy your server |
| [Reference](reference.md) | Data structures and config |
| [Config](config.md) | Server configuration options |
| [Errors](errors.md) | Common error messages |

---

## Commands

All commands documented individually in `docs/commands/`.

### Text Messaging

| Command | Description |
|---------|-------------|
| [`message_new`](commands/message_new.md) | Send a message |
| [`message_edit`](commands/message_edit.md) | Edit your message |
| [`message_delete`](commands/message_delete.md) | Delete a message |
| [`messages_get`](commands/messages_get.md) | Get channel messages |
| [`message_get`](commands/message_get.md) | Get a specific message |
| [`messages_search`](commands/messages_search.md) | Search messages |
| [`messages_pinned`](commands/messages_pinned.md) | Get pinned messages |
| [`message_pin`](commands/message_pin.md) | Pin a message |
| [`message_unpin`](commands/message_unpin.md) | Unpin a message |
| [`message_react_add`](commands/message_react_add.md) | Add reaction |
| [`message_react_remove`](commands/message_react_remove.md) | Remove reaction |
| [`message_replies`](commands/message_replies.md) | Get message replies |
| [`typing`](commands/typing.md) | Send typing indicator |

### Threads (Forum Channels)

| Command | Description |
|---------|-------------|
| [`thread_create`](commands/thread_create.md) | Create a thread |
| [`thread_get`](commands/thread_get.md) | Get thread details |
| [`thread_messages`](commands/thread_messages.md) | Get thread messages |
| [`thread_update`](commands/thread_update.md) | Update a thread |
| [`thread_delete`](commands/thread_delete.md) | Delete a thread |
| [`thread_join`](commands/thread_join.md) | Join a thread |
| [`thread_leave`](commands/thread_leave.md) | Leave a thread |

### Voice Channels

| Command | Description |
|---------|-------------|
| [`voice_join`](commands/voice_join.md) | Join voice channel |
| [`voice_leave`](commands/voice_leave.md) | Leave voice channel |
| [`voice_mute`](commands/voice_mute.md) | Mute/unmute yourself |
| [`voice_state`](commands/voice_state.md) | Get voice participants |

### Users

| Command | Description |
|---------|-------------|
| [`users_list`](commands/users_list.md) | List all users |
| [`users_online`](commands/users_online.md) | List online users |
| [`status_set`](commands/status_set.md) | Set your status |
| [`status_get`](commands/status_get.md) | Get user status |
| [`pings_get`](commands/pings_get.md) | Get your pings |

### Channels

| Command | Description |
|---------|-------------|
| [`channels_get`](commands/channels_get.md) | Get available channels |
| [`channel_create`](commands/channel_create.md) | Create channel (owner) |
| [`channel_update`](commands/channel_update.md) | Update channel (owner) |
| [`channel_move`](commands/channel_move.md) | Move channel (owner) |
| [`channel_delete`](commands/channel_delete.md) | Delete channel (owner) |

### Roles & Permissions

| Command | Description |
|---------|-------------|
| [`roles_list`](commands/roles_list.md) | List all roles |
| [`role_create`](commands/role_create.md) | Create role (owner) |
| [`role_update`](commands/role_update.md) | Update role (owner) |
| [`role_reorder`](commands/role_reorder.md) | Reorder roles (owner) |
| [`role_delete`](commands/role_delete.md) | Delete role (owner) |
| [`user_roles_set`](commands/user_roles_set.md) | Set user roles (owner) |
| [`user_roles_get`](commands/user_roles_get.md) | Get user's roles |

### User Management (Owner)

| Command | Description |
|---------|-------------|
| [`user_ban`](commands/user_ban.md) | Ban a user |
| [`user_unban`](commands/user_unban.md) | Unban a user |
| [`users_banned_list`](commands/users_banned_list.md) | List banned users |
| [`user_timeout`](commands/user_timeout.md) | Timeout a user |
| [`user_leave`](commands/user_leave.md) | Disconnect a user |
| [`user_update`](commands/user_update.md) | Update user data |
| [`user_delete`](commands/user_delete.md) | Delete user |

### Nicknames

| Command | Description |
|---------|-------------|
| [`nickname_update`](commands/nickname_update.md) | Set nickname |
| [`nickname_remove`](commands/nickname_remove.md) | Remove nickname |

### Emojis

| Command | Description |
|---------|-------------|
| [`emoji_add`](commands/emoji_add.md) | Add custom emoji |
| [`emoji_get_all`](commands/emoji_get_all.md) | Get all emojis |
| [`emoji_get_id`](commands/emoji_get_id.md) | Get emoji by ID |
| [`emoji_get_filename`](commands/emoji_get_filename.md) | Get emoji by filename |
| [`emoji_update`](commands/emoji_update.md) | Update emoji |
| [`emoji_delete`](commands/emoji_delete.md) | Delete emoji |

### Slash Commands

| Command | Description |
|---------|-------------|
| [`slash_register`](commands/slash_register.md) | Register a slash command |
| [`slash_list`](commands/slash_list.md) | List slash commands |
| [`slash_call`](commands/slash_call.md) | Execute a slash command |
| [`slash_response`](commands/slash_response.md) | Respond to slash command |

### Webhooks

| Command | Description |
|---------|-------------|
| [`webhook_create`](commands/webhook_create.md) | Create webhook |
| [`webhook_list`](commands/webhook_list.md) | List webhooks |
| [`webhook_get`](commands/webhook_get.md) | Get webhook |
| [`webhook_update`](commands/webhook_update.md) | Update webhook |
| [`webhook_delete`](commands/webhook_delete.md) | Delete webhook |
| [`webhook_regenerate`](commands/webhook_regenerate.md) | Regenerate webhook token |

### Push Notifications

| Command | Description |
|---------|-------------|
| [`push_get_vapid`](commands/push_get_vapid.md) | Get VAPID public key |
| [`push_subscribe`](commands/push_subscribe.md) | Subscribe to push |
| [`push_unsubscribe`](commands/push_unsubscribe.md) | Unsubscribe from push |

### Server Management

| Command | Description |
|---------|-------------|
| [`ping`](commands/ping.md) | Ping the server |
| [`server_info`](commands/server_info.md) | Get server info |
| [`server_update`](commands/server_update.md) | Update server info (owner) |
| [`plugins_list`](commands/plugins_list.md) | List plugins |
| [`plugins_reload`](commands/plugins_reload.md) | Reload plugins |
| [`rate_limit_status`](commands/rate_limit_status.md) | Check rate limit |
| [`rate_limit_reset`](commands/rate_limit_reset.md) | Reset rate limit (owner) |
| [`auth`](commands/auth.md) | Authenticate |
| [`events`](commands/events.md) | Get server events |

### Embeds

| Command | Description |
|---------|-------------|
| [`embeds_list`](commands/embeds_list.md) | List embeds |

---

## Data Structures

| Structure | Description |
|-----------|-------------|
| [User](data/user.md) | User object format |
| [Channel](data/channels.md) | Channel configuration |
| [Message](data/messages.md) | Message structure |
| [Role](data/roles.md) | Role definition |
| [Emoji](data/emojis.md) | Custom emoji |
| [Permissions](data/permissions.md) | Permission system |

---

## Slash Commands (Built-in)

Users can use these slash commands:

| Command | Description | Docs |
|---------|-------------|------|
| `/help` | Show available commands | [slash_help](slash/slash_help.md) |
| `/nick <name>` | Change nickname | [slash_nick](slash/slash_nick.md) |
| `/ban <user>` | Ban a user | [slash_ban](slash/slash_ban.md) |
| `/unban <user>` | Unban a user | [slash_unban](slash/slash_unban.md) |
| `/mute <user>` | Mute a user | [slash_mute](slash/slash_mute.md) |
| `/unmute <user>` | Unmute a user | [slash_unmute](slash/slash_unmute.md) |
| `/role <user> <role>` | Assign a role | [slash_role](slash/slash_role.md) |
| `/channel <name>` | Create channel | [slash_channel](slash/slash_channel.md) |

---

## Other Resources

- [Push Notifications Guide](push_notifications.md) - Web Push setup
- [Welcome Plugin](plugins/welcome.md) - Example plugin
- [User Join/Leave Events](events/user_join_leave.md) - Event handling

---

**Last Updated:** 2026-03-28
