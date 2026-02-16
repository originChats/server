# Command: channel_delete

Delete a channel from the server (owner only).

## Request

```json
{
  "cmd": "channel_delete",
  "name": "channel_name"
}
```

### Fields

- `name`: (required) The name of the channel to delete.

## Response

### On Success

```json
{
  "cmd": "channel_delete",
  "name": "channel_name",
  "deleted": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Channel name is required"}`
- `{"cmd": "error", "val": "Channel not found"}`

## Notes

- Requires `owner` role.
- **Permanent action** - Deleted channels cannot be recovered.
- Deleting a text channel permanently removes all messages stored in it.
- Deleting a voice channel removes it from the voice channel list.
- Deleting a separator removes it from the channel list.
- Connected users in the channel will remain but the channel will no longer appear.
- The channel file is deleted from disk (for text/voice channels).
- Use with caution - this action is irreversible.

## See Also

- [channel_create](channel_create.md) - Create a new channel
- [channel_update](channel_update.md) - Update a channel
- [channel_move](channel_move.md) - Move a channel

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "channel_delete":`).
