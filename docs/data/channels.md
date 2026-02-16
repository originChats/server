# Channel Object Structure

A channel object represents a chat channel in OriginChats. Channels can be text or voice channels.

## Base Channel Object

```json
{
  "type": "text",
  "name": "general",
  "display_name": "General Chat",
  "icon": "https://example.com/icon.png",
  "description": "General chat channel for everyone",
  "permissions": {
    "view": ["user"],
    "send": ["user"],
    "delete": ["admin", "moderator"],
    "delete_own": ["user"],
    "edit_own": ["user"]
  }
}
```

### Fields

- `type`: Channel type. Can be `"text"` or `"voice"`.
- `name`: Channel name (string), used as unique identifier.
- `display_name`: Display name for the channel. If present, this should be displayed instead of `name` in the UI.
- `icon`: HTTP/HTTPS URL for the image displayed on a channel.
- `description`: Description of the channel.
- `permissions`: Object with arrays of roles for each action.
  - `view`: Roles that can view/access the channel.
  - `send`: Roles that can send messages (text channels only).
  - `delete`: Roles that can delete any message.
  - `delete_own`: (optional) Roles allowed to delete their own messages. If not present, all roles can delete their own messages by default.
  - `edit_own`: (optional) Roles allowed to edit their own messages. If not present, all roles can edit their own messages by default.
  - `react`: (optional) Roles allowed to add/remove reactions.

---

## Text Channels

Text channels support real-time messaging with:
- Send/receive messages
- Edit and delete messages
- Replies and threading
- Reactions
- Pinning messages
- Message search

---

## Voice Channels

Voice channels support audio communication via WebRTC:

### Voice Channel Object (from `channels_get`)

```json
{
  "type": "voice",
  "name": "lounge",
  "display_name": "Chat Lounge",
  "icon": "...",
  "description": "Voice hangout",
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
```

### Voice State Fields

- `voice_state`: (optional) Array of participants currently in the voice channel.
  - Only sent for channels the requesting user is in.
  - Each participant contains:
    - `username`: Participant's display name.
    - `muted`: Whether their microphone is muted.

**Note:** The `peer_id` field is NOT included in `voice_state` for security and data efficiency. Use the `voice_join`/`voice_state` commands to get peer IDs when joining a channel.

### Voice Channel Behavior

- **Join/Leave:** Users can join and leave voice channels freely
- **Participants List:** Users with `view` permission can see who's in the channel
- **Audio Streaming:** Uses WebRTC peer-to-peer connections
- **Mute:** Users can mute/unmute their microphone
- **View-Only Mode:** Users can view voice channel participants without joining

---

## Permissions

See [permissions documentation](permissions.md) for details on how permissions work.

---

## Related Commands

- Text Channels: [message_new](../commands/message_new.md), [messages_get](../commands/messages_get.md)
- Voice Channels: [voice_join](../commands/voice_join.md), [voice_state](../commands/voice_state.md)
- Channel List: [channels_get](../commands/channels_get.md)

