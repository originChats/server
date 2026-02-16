# Command: voice_state

Get the current participants in a voice channel.

## Request

```json
{
  "cmd": "voice_state",
  "channel": "<channel_name>"
}
```

### Fields

- `channel`: (required) Name of the voice channel.

## Response

### On Success

```json
{
  "cmd": "voice_state",
  "channel": "<channel_name>",
  "participants": [
    {
      "id": "USR:1234567890abcdef",
      "username": "alice",
      "peer_id": "...",     // Only if you're in the channel
      "muted": false
    },
    {
      "id": "USR:0987654321fedcba",
      "username": "bob",
      "peer_id": "...",     // Only if you're in the channel
      "muted": true
    }
  ]
}
```

### Participant Fields

- `id`: User ID.
- `username`: Display name.
- `peer_id`: WebRTC peer ID (included only if you're currently IN the voice channel).
- `muted`: Whether their microphone is muted.

**Important:** If you're a viewer (not in the channel), you receive participant data WITHOUT `peer_id` fields. Join the channel to receive `peer_id` for P2P connections.

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Channel name is required"}`
- `{"cmd": "error", "val": "User not found"}`
- `{"cmd": "error", "val": "You do not have permission to view this voice channel"}`
- `{"cmd": "error", "val": "This is not a voice channel"}`
- `{"cmd": "error", "val": "Server data not available"}`

## Notes

- User must have `view` permission on the channel.
- Returns empty participant list if channel has nobody in it.
- `peer_id` is only exposed to actual channel participants for privacy/security.
- Use this command before joining to see who's in a channel.
- Participants include yourself once you've joined.

## Use Cases

1. **Before Joining:** Check who's in a voice channel before joining.
2. **Monitoring:** Periodically fetch to see who joins/leaves without joining yourself (view-only mode).
3. **Connection Setup:** Use `peer_id` (when in channel) to establish WebRTC connections.

## Live Updates

For real-time participant updates, listen for these broadcast events:

- `voice_user_joined` - Sent when a user joins the channel.
- `voice_user_left` - Sent when a user leaves the channel.
- `voice_user_updated` - Sent when a user mutes/unmutes.

## See Also

- [voice_join](voice_join.md) - Join a voice channel and receive peer_ids
- [voice_mute](voice_mute.md) - Mute/unmute microphone
- [Data: Channel Voice State](../data/channels.md#voice-channels)

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "voice_state":`).
