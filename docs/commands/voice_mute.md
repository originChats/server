# Command: voice_mute / voice_unmute

Allows a user to mute/unmute their microphone in the current voice channel.

## Requests

### Mute Microphone

```json
{
  "cmd": "voice_mute"
}
```

### Unmute Microphone

```json
{
  "cmd": "voice_unmute"
}
```

No additional parameters required. The user mutes/unmutes their microphone in their currently joined voice channel.

## Responses

### On Success (Mute)

```json
{
  "cmd": "voice_mute",
  "channel": "<channel_name>",
  "muted": true
}
```

### On Success (Unmute)

```json
{
  "cmd": "voice_unmute",
  "channel": "<channel_name>",
  "muted": false
}
```

## Broadcast

### Voice User Updated

When a user mutes/unmutes, all clients with view permission receive:

```json
{
  "type": "voice_user_updated",
  "channel": "<channel_name>",
  "user": {
    "id": "USR:1234567890abcdef",
    "username": "<username>",
    "peer_id": "...",     // Only for channel participants
    "muted": true       // or false
  },
  "global": true
}
```

- **Channel participants** receive the user object with `peer_id`.
- **Viewers only** receive the user object WITHOUT `peer_id`.

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Server data not available"}`
- `{"cmd": "error", "val": "You are not in a voice channel"}`
- `{"cmd": "error", "val": "Voice channel no longer exists"}`
- `{"cmd": "error", "val": "You are not in this voice channel"}`

## Notes

- User must be currently in a voice channel.
- Muting stops sending audio to other participants but keeps you in the channel.
- You can still hear others when muted.
- Clients should display mute status in their UI.
- The mute state is included in `voice_state` participant data.

## See Also

- [voice_join](voice_join.md) - Join a voice channel
- [voice_state](voice_state.md) - Get voice channel participants with mute status

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "voice_mute" | "voice_unmute":`).
