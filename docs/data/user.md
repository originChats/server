# User Object Structure

A user object represents a user in OriginChats. User objects are sent in various responses and broadcasts.

## Basic User Object (for API responses)

```json
{
  "username": "alice",
  "roles": ["user", "moderator"],
  "id": "USR:1234567890abcdef"
}
```

- `username`: User's display name (string).
- `roles`: Array of role names assigned to the user.
- `id`: Unique user ID from Rotur (string).

## User Connection Broadcast

When a user connects, all clients receive a broadcast:

```json
{
  "cmd": "user_connect",
  "user": {
    "username": "alice",
    "roles": ["user", "moderator"],
    "color": "#00aaff"
  }
}
```

- `color`: Hex color of the user's primary role (string).

## Ready Packet (After Authentication)

After successful authentication, the client receives:

```json
{
  "cmd": "ready",
  "user": {
    "username": "alice",
    "roles": ["user", "moderator"],
    "id": "USR:1234567890abcdef"
  }
}
```

## Voice Channel Participant

In voice channel operations, participants are represented as:

```json
{
  "id": "USR:1234567890abcdef",
  "username": "alice",
  "peer_id": "...",
  "muted": false
}
```

- `peer_id`: WebRTC peer ID for establishing P2P connections (only sent to channel participants).
- `muted`: Whether the user's microphone is muted.

**Note:** Viewers (users viewing but not in the voice channel) receive the user data WITHOUT `peer_id`.

## User Disconnect Broadcast

When a user disconnects, all clients receive:

```json
{
  "cmd": "user_disconnect",
  "username": "alice"
}
```

---

## Role Resolution

User roles are fetched from the database when needed:
- Role colors are resolved from the first role in the user's role list
- Default to `null` if no roles or color is set

**Example:**

```python
user_roles = user.get("roles", [])
first_role_name = user_roles[0] if user_roles else None
color = roles.get_role(first_role_name).get("color") if first_role_name else None
```

---

## See Also

- [Role Object](roles.md) - Role structure and colors
- [Channel Permissions](permissions.md) - How roles control access
- [Voice Commands](../commands/voice_join.md) - Voice channel participant management
