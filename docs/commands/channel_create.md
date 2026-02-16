# Command: channel_create

Create a new channel (owner only).

## Request

### Text Channel

```json
{
  "cmd": "channel_create",
  "name": "channel_name",
  "type": "text",
  "description": "Channel description",
  "wallpaper": "https://example.com/image.png",
  "permissions": {
    "view": ["user"],
    "send": ["user"],
    "delete": ["admin"]
  }
}
```

### Voice Channel

```json
{
  "cmd": "channel_create",
  "name": "voice_channel",
  "type": "voice",
  "description": "Voice channel for talking",
  "permissions": {
    "view": ["user"],
    "connect": ["user"]
  }
}
```

### Separator

```json
{
  "cmd": "channel_create",
  "name": "separator",
  "type": "separator",
  "size": 10,
  "permissions": {
    "view": ["user"]
  }
}
```

### Fields

- `name`: (required) The name of the new channel. Must be unique.
- `type`: (required) Channel type: `text`, `voice`, or `separator`.
- `description`: (optional) Channel description (not for separators).
- `wallpaper`: (optional) Wallpaper URL for text/voice channels.
- `permissions`: (optional) Channel permissions object. Defaults to owner-only access if omitted.
- `size`: (optional) Separator size in pixels (for separator type only).

## Response

### On Success

```json
{
  "cmd": "channel_create",
  "channel": {
    "name": "channel_name",
    "type": "text",
    "description": "...",
    "permissions": {...}
  },
  "created": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Channel name is required"}`
- `{"cmd": "error", "val": "Channel type is required (text, voice, or separator)"}`
- `{"cmd": "error", "val": "Invalid channel type, must be text, voice, or separator"}`
- `{"cmd": "error", "val": "Channel already exists"}`
- `{"cmd": "error", "val": "Failed to create channel"}`

## Notes

- Requires `owner` role.
- Channel names are case-sensitive.
- For text channels, an empty message file is automatically created.
- Voice channels support WebRTC peer-to-peer audio connections.
- Separators are visual dividers in the channel list.
- Default permissions allow only `owner` role to view and use the channel.
- If permissions are omitted, they default to owner-only access.
- Use `channel_move` to reorder channels after creation.

## See Also

- [channel_update](channel_update.md) - Update a channel
- [channel_move](channel_move.md) - Move a channel to a new position
- [channel_delete](channel_delete.md) - Delete a channel
- [channels_get](channels_get.md) - Get all channels

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "channel_create":`).
