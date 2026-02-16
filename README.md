# OriginChats Server

A WebSocket-based real-time chat server with voice channels, slash commands, role-based permissions, and plugin support.

## Features

- **Text Messaging** - Real-time messaging with replies, reactions, and search
- **Voice Channels** - WebRTC peer-to-peer audio
- **User Management** - Roles, permissions, bans, timeouts
- **Rate Limiting** - Built-in spam protection
- **Plugins** - Extensible plugin system
- **Slash Commands** - Custom command handlers

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure:**
   - Edit `config.json` for server settings
   - Set up Rotur authentication service

3. **Run:**
   ```bash
   python init.py
   ```

## Project Structure

```
originChats/
├── init.py                 # Entry point
├── server.py              # WebSocket server
├── config.json            # Server configuration
├── watchers.py            # File system watchers
├── db/                    # Database modules
│   ├── channels.py        # Channel management
│   ├── users.py           # User management
│   ├── roles.py           # Role management
│   └── *.json             # Data files
├── handlers/              # Request handlers
│   ├── auth.py            # Authentication
│   ├── message.py         # Command router
│   ├── websocket_utils.py # WebSocket utilities
│   └── rate_limiter.py    # Rate limiting
├── plugins/               # Plugin examples
└── docs/                  # Documentation
    ├── client-development/
    ├── commands/
    └── data/
```

## Documentation

- **[API Documentation](docs/)** - Complete API reference for client developers
  - [Getting Started](docs/README.md#getting-started)
  - [All Commands](docs/README.md#commands)
  - [Data Structures](docs/README.md#data-structures)
  - [Client Development Guide](docs/client-development/getting-started.md)
  - [Voice Channels Implementation](docs/client-development/voice.md)

## Configuration

Key settings in `config.json`:

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
    "messages_per_minute": 30,
    "burst_limit": 5,
    "cooldown_seconds": 60
  },
  "limits": {
    "post_content": 2000
  }
}
```

See [Config Schema](docs/data/config.md) for full configuration options.

## Rate Limiting

OriginChats includes built-in rate limiting to prevent spam:

- **Per-minute limit:** Maximum messages per user per minute (configurable)
- **Burst protection:** Prevents spam in short time windows
- **Cooldown:** Temporary restriction after burst limit exceeded

Rate limited users receive:
```json
{
  "cmd": "rate_limit",
  "length": <milliseconds>
}
```

## Channel Types

### Text Channels
- Send/receive messages
- Edit/delete own messages
- Add reactions
- Reply to messages
- Pin/unpin messages
- Search messages

### Voice Channels
- WebRTC peer-to-peer audio
- Join/leave freely
- Mute/unmute
- View participants without joining

## Permissions

Role-based permission system for:

- View channels
- Send messages
- Edit own messages
- Delete messages (own and others)
- Pin messages
- Add reactions
- Administrative actions (ban, timeout, etc.)

See [Permissions System](docs/data/permissions.md) for details.

## Authentication

OriginChats integrates with the Rotur authentication service:

1. Server sends handshake with `validator_key`
2. Client obtains validator from Rotur
3. Client sends validator to server
4. Server validates via Rotur API
5. User is authenticated

See [Authentication Guide](docs/auth.md) for full flow.

## Clients

Check out the [client list](clients.md) for official and community clients:

## Development

### Adding New Commands

1. Add a new case in [`handlers/message.py`](handlers/message.py):
   ```python
   case "my_command":
       # Handle command
       return {"cmd": "my_response"}
   ```

2. Update documentation in `docs/commands/my_command.md`

### Creating Plugins

See `plugins/` directory for examples. Plugins can:
- Respond to new messages
- Handle slash commands
- Modify message data
- Trigger events

## API Protocol

All WebSocket messages follow this format:

```json
{
  "cmd": "command_name",
  "key": "value",
  "global": true  // Optional: broadcast to all
}
```

See [Protocol Documentation](docs/protocol.md) for details.

## Error Handling

All errors return:

```json
{
  "cmd": "error",
  "val": "Error message"
}
```

See [Error Handling](docs/errors.md) for all possible errors.

## Contributing

Contributions are welcome! Areas of contribution:

- Bug fixes
- New commands
- Plugin examples
- Documentation improvements
- Client implementations

## License

See LICENSE file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/...)
- 💬 [Discord](https://discord.gg/...)

