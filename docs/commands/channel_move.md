# Command: channel_move

Move a channel to a new position in the channel list (owner only).

## Request

```json
{
  "cmd": "channel_move",
  "name": "channel_name",
  "position": 0
}
```

### Fields

- `name`: (required) The name of the channel to move.
- `position`: (required) The new position for the channel (0-based index).

## Response

### On Success

```json
{
  "cmd": "channel_move",
  "name": "channel_name",
  "position": 0,
  "moved": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Channel name is required"}`
- `{"cmd": "error", "val": "Position is required"}`
- `{"cmd": "error", "val": "Position must be a non-negative integer"}`
- `{"cmd": "error", "val": "Channel not found"}`

## Notes

- Requires `owner` role.
- Channel positions are 0-based (first channel is position 0).
- Moving a channel to position 0 makes it the first channel in the list.
- Moving a channel beyond the last position will place it at the end.
- Other channels shift positions automatically to maintain order.
- Separators maintain their positions as channels move around them.
- The channel list is updated immediately and sent to all clients.

## See Also

- [channel_create](channel_create.md) - Create a new channel
- [channel_update](channel_update.md) - Update a channel
- [channel_delete](channel_delete.md) - Delete a channel

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "channel_move":`).
