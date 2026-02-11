# Channel Object Structure

A channel object represents a chat channel. Example structure:

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

- `type`: Channel type (e.g., `text`).
- `name`: Channel name (string).
- `display_name`: Display name for the channel. If present, this should be displayed instead of `name` in the UI.
- `icon`: HTTP/HTTPS URL for the image displayed on a channel.
- `description`: Description of the channel.
- `permissions`: Object with arrays of roles for each action (`view`, `send`, `delete`, `delete_own`, `edit_own`).
  - `delete_own`: (optional) Roles allowed to delete their own messages. If not present, all roles can delete their own messages by default.
  - `edit_own`: (optional) Roles allowed to edit their own messages. If not present, all roles can edit their own messages by default.

**Permissions:** See [permissions documentation](permissions.md) for details on how permissions work.

Returned by: [channels_get](../commands/channels_get.md)
