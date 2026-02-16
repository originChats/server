# Command: channel_update

Update an existing channel's properties (owner only).

## Request

### Update Name

```json
{
  "cmd": "channel_update",
  "current_name": "old_name",
  "updates": {
    "name": "new_name"
  }
}
```

### Update Multiple Fields

```json
{
  "cmd": "channel_update",
  "current_name": "channel_name",
  "updates": {
    "name": "new_name",
    "description": "New description",
    "permissions": {
      "view": ["user"],
      "send": ["admin"],
      "delete": ["owner"]
    },
    "wallpaper": "https://example.com/new-image.png"
  }
}
```

### Fields

- `current_name`: (required) The current name of the channel to update.
- `updates`: (required) Object containing the fields to update:
  - `name`: (optional) New channel name. Renames the channel.
  - `description`: (optional) New channel description.
  - `permissions`: (optional) New channel permissions object.
  - `wallpaper`: (optional) New wallpaper URL.
  - `type`: (optional) New channel type (text/voice/separator).
  - `size`: (optional) New separator size (for separators only).

## Response

### On Success

```json
{
  "cmd": "channel_update",
  "channel": {
    "name": "new_name",
    "type": "text",
    "description": "New description",
    "permissions": {...},
    "wallpaper": "..."
  },
  "updated": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "current_name is required"}`
- `{"cmd": "error", "val": "updates object is required"}`
- `{"cmd": "error", "val": "Channel not found"}`
- `{"cmd": "error", "val": "Invalid channel type"}`
- `{"cmd": "error", "val": "Channel with new name already exists"}`
- `{"cmd": "error", "val": "Failed to update channel"}`

## Notes

- Requires `owner` role.
- Channel names are case-sensitive.
- When renaming a channel, the channel file is also renamed for text/voice channels.
- `current_name` is used to find the channel in case multiple updates are being applied.
- You can update multiple fields in a single request.
- When changing permissions, all roles need to be specified (not merged with existing permissions).
- Separator channels can be converted to text/voice channels by changing the type.
- Messages stored in the channel are preserved when renaming.

## See Also

- [channel_create](channel_create.md) - Create a new channel
- [channel_move](channel_move.md) - Move a channel to a new position
- [channel_delete](channel_delete.md) - Delete a channel

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "channel_update":`).
