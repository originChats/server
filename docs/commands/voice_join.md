# Command: voice_join

Allows a user to join a voice channel and establish WebRTC peer connections.

## Request

```json
{
  "cmd": "voice_join",
  "channel": "<channel_name>",
  "peer_id": "<your_peer_id>"
}
```

### Fields

- `channel`: (required) Name of the voice channel to join.
- `peer_id`: (required) Your WebRTC peer ID for P2P connections.

## Response

### On Success

```json
{
  "cmd": "voice_join",
  "channel": "<channel_name>",
  "participants": [
    {
      "username": "alice",
      "peer_id": "...",
      "muted": false
    },
    {
      "username": "bob",
      "peer_id": "...",
      "muted": true
    }
  ]
}
```

The `participants` array contains all current participants **except yourself**. Each participant includes:
- `username`: Participant's display name.
- `peer_id`: Their WebRTC peer ID (for establishing P2P connection).
- `muted`: Whether their microphone is muted.

## Broadcasts

### Voice User Joined

When a user joins a voice channel, all clients with view permission receive:

```json
{
  "cmd": "voice_user_joined",
  "channel": "<channel_name>",
  "user": {
    "id": "USR:1234567890abcdef",
    "username": "<username>",
    "peer_id": "...",     // Only for channel participants
    "muted": false
  },
  "global": true
}
```

- **Channel participants** receive the user object with `peer_id`.
- **Viewers only** (users viewing but not in channel) receive the user object WITHOUT `peer_id`.

### Voice User Left

If the user was already in another voice channel, a `voice_user_left` broadcast is sent for the old channel first.

```json
{
  "cmd": "voice_user_left",
  "channel": "<old_channel_name>",
  "username": "<username>",
  "global": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Channel name is required"}`
- `{"cmd": "error", "val": "Peer ID is required"}`
- `{"cmd": "error", "val": "User not found"}`
- `{"cmd": "error", "val": "You do not have permission to join this voice channel"}`
- `{"cmd": "error", "val": "This is not a voice channel"}`

## Notes

- User must be authenticated.
- User must have `view` permission on the channel.
- If user is already in a voice channel, they will leave it automatically before joining the new one.
- Your own `peer_id` should be unique and used by other clients to connect to your audio stream.
- Use `voice_state` command to get current participants before joining.

## See Also

- [voice_leave](voice_leave.md) - Leave a voice channel
- [voice_state](voice_state.md) - Get voice channel participants
- [voice_mute](voice_mute.md) - Mute/unmute your microphone
- [Data: Channel Object](../data/channels.md#voice-channels)

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "voice_join":`).
