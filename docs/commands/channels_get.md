# Command: channels_get

Get all channels the user has access to.

## Request

```json
{
  "cmd": "channels_get"
}
```

No additional parameters required.

## Response

### On Success

```json
{
  "cmd": "channels_get",
  "val": [
    {
      "name": "general",
      "type": "text",
      "display_name": "General Chat",
      "icon": "https://example.com/icon.png",
      "description": "General chat for everyone",
      "permissions": {
        "view": ["user"],
        "send": ["user"],
        "delete": ["admin"],
        "delete_own": ["user"],
        "edit_own": ["user"],
        "react": ["user"],
        "pin": ["user"]
      }
    },
    {
      "name": "voice-lounge",
      "type": "voice",
      "display_name": "Voice Lounge",
      "icon": "...",
      "description": "Voice hangout channel",
      "permissions": {
        "view": ["user"]
      },
      "voice_state": [
        {
          "username": "alice",
          "muted": false
        },
        {
          "username": "bob",
          "muted": true
        }
      ]
    }
    // ... more channels
  ]
}
```

### Channel Object Fields

- `name`: Unique channel identifier (string)
- `type`: Channel type - either `"text"` or `"voice"`
- `display_name`: Display name for UI (optional)
- `icon`: HTTP/HTTPS URL for channel icon (optional)
- `description`: Channel description (optional)
- `permissions`: Object mapping action types to allowed role arrays
  - `view`: Roles that can see/access the channel
  - `send`: Roles that can send messages (text channels only)
  - `delete`: Roles that can delete any message
  - `delete_own`: Roles that can delete their own messages
  - `edit_own`: Roles that can edit their own messages
  - `react`: Roles that can add/remove reactions (optional)
  - `pin`: Roles that can pin messages (optional)
- `voice_state`: (**Only on voice channels where you're a participant**) Array of other users currently in the voice channel

### Voice State Fields

For voice channels where the requesting user is currently a participant:

- `voice_state` array contains participants OTHER than yourself
- Each participant object has:
  - `username`: Participant's display name
  - `muted`: Whether their microphone is muted

**Note:** `voice_state` is NOT included for:
- Text channels
- Voice channels you're not currently in
- When you have view permission but haven't joined the voice channel

## Error Responses

- `{"cmd": "error", "val": "User not authenticated"}`
- `{"cmd": "error", "val": "User not found"}`

## Notes

- User must be authenticated.
- Only returns channels where the user has `view` permission based on their roles.
- For voice channels, `voice_state` is only included if you're actively joined (not just viewing).
- Channels are returned in the order defined in the channel index (usually alphabetical or custom order).
- Use `voice_state` to quickly see who's in voice channels you're currently in.
- To see voice channel participants without joining, use the `voice_state` command instead.

## See Also

- [voice_state](voice_state.md) - Get participants in a voice channel (even if you're not in it)
- [messages_get](messages_get.md) - Get messages from a text channel
- [Data: Channel Object](../data/channels.md) - Full channel structure reference

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "channels_get":`).

