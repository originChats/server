# Channel Object Structure

A channel object represents a chat channel in OriginChats. Channels can be text, voice, forum, or separator channels.

## Base Channel Object

```json
{
  "type": "text",
  "name": "general",
  "display_name": "General Chat",
  "description": "General chat channel for everyone",
  "permissions": {
    "view": ["user"],
    "send": ["user"],
    "delete": ["admin", "moderator"],
    "delete_own": ["user"],
    "edit_own": ["user"],
    "pin": ["admin"],
    "react": ["user"],
    "create_thread": ["user"]
  }
}
```

### Fields

- `type`: Channel type. Can be `"text"`, `"voice"`, `"forum"`, or `"separator"`.
- `name`: Channel name (string), used as unique identifier.
- `display_name`: (optional) Display name for the channel. If present, this should be displayed instead of `name` in the UI.
- `description`: (optional) Description of the channel.
- `permissions`: Object with arrays of roles for each action.
    - `view`: Roles that can view/access the channel.
    - `send`: Roles that can send messages (text channels only).
    - `delete`: Roles that can delete any message.
    - `delete_own`: (optional) Roles allowed to delete their own messages. If not present, all roles can delete their own messages by default.
    - `edit_own`: (optional) Roles allowed to edit their own messages. If not present, all roles can edit their own messages by default.
    - `pin`: (optional) Roles allowed to pin messages in the channel. If not present, only the owner can pin messages by default.
    - `react`: (optional) Roles allowed to add/remove reactions.
    - `create_thread`: (optional) Roles allowed to create threads in forum channels.

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

## Forum Channels

Forum channels are special channels where users cannot send messages directly. Instead, users create threads within the channel.

### Forum Channel Object

```json
{
    "type": "forum",
    "name": "announcements",
    "description": "Server announcements and updates",
    "permissions": {
        "view": ["user"],
        "create_thread": ["user"]
    },
    "threads": [
        {
            "id": "uuid-here",
            "name": "Welcome to the server!",
            "parent_channel": "announcements",
            "created_by": "admin",
            "created_at": 1234567890.123,
            "locked": false,
            "archived": false,
            "last_message": 1234567900.456,
            "last_message_id": "msg_uuid_here"
        }
    ]
}
```

### Forum Channel Behavior

- **No Direct Messages:** Users cannot send messages directly in a forum channel.
- **Thread Creation:** Users with `create_thread` permission can create new threads.
- **Thread List:** When fetching channels, forum channels include an array of threads.
- **Thread Messages:** Messages are sent and received within threads using the `thread_id` parameter.

### Creating Threads

Use the `thread_create` command to create a new thread in a forum channel.

---

## Voice Channels

Voice channels support audio communication via WebRTC:

### Voice Channel Object (from `channels_get`)

```json
{
  "type": "voice",
  "name": "lounge",
  "display_name": "Chat Lounge",
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

## Separator Channels

Separator channels are visual dividers in the channel list.

```json
{
    "type": "separator",
    "size": 10,
    "permissions": {
        "view": ["user"]
    }
}
```

### Separator Fields

- `size`: Height of the separator in pixels.

---

## Permissions

See [permissions documentation](permissions.md) for details on how permissions work.

---

## Related Commands

- Text Channels: [message_new](../commands/message_new.md), [messages_get](../commands/messages_get.md)
- Forum Channels: [thread_create](../commands/thread_create.md), [thread_get](../commands/thread_get.md)
- Voice Channels: [voice_join](../commands/voice_join.md), [voice_state](../commands/voice_state.md)
- Channel List: [channels_get](../commands/channels_get.md)

