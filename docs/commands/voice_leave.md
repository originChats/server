# Command: voice_leave

Allows a user to leave their current voice channel.

## Request

```json
{
  "cmd": "voice_leave"
}
```

No additional parameters required. The user leaves their currently joined voice channel.

## Response

### On Success

```json
{
  "cmd": "voice_leave",
  "channel": "<channel_name>"
}
```

## Broadcast

### Voice User Left

When a user leaves a voice channel, all clients with view permission receive:

```json
{
  "type": "voice_user_left",
  "channel": "<channel_name>",
  "username": "<username>",
  "global": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "You are not in a voice channel"}`
- `{"cmd": "error", "val": "Voice channel no longer exists"}`

## Notes

- User must be currently in a voice channel.
- If the voice channel has been deleted or the user's session is stale, an error is returned.
- When disconnected from the server, users are automatically removed from their voice channel.

## See Also

- [voice_join](voice_join.md) - Join a voice channel
- [voice_state](voice_state.md) - Check voice channel participants

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "voice_leave":`).
