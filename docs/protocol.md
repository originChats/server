# OriginChats: Additional Protocol & Client Setup Documentation

This page documents protocol details and server packets not covered elsewhere, useful for client developers.

---

## Handshake Packet

When a client connects, the server sends a handshake packet before authentication:

```json
{
  "cmd": "handshake",
  "val": {
    "server": { ... },        // Server info from config.json
    "limits": { ... },        // Message/content limits
    "version": "1.1.0",     // Server version
    "validator_key": "originChats-<key>" // Used for Rotur validation
  }
}
```

- The client should use this to display server info and prepare for authentication.

---

## Authentication Flow

1. **Client sends:** `{ "cmd": "auth", "validator": "<token>" }`
2. **Server responds:**
   - On success: `{ "cmd": "auth_success", "val": "Authentication successful" }`
   - On failure: `{ "cmd": "auth_error", "val": "<reason>" }`
   - On success, also: `{ "cmd": "ready", "user": { ...user object... } }`

See [Authentication](auth.md) for full details.

---

## User Connection Broadcasts

### User Connect

When a user connects, all clients receive:

```json
{
  "cmd": "user_connect",
  "user": {
    "username": "<username>",
    "roles": [ ... ],
    "color": "#RRGGBB" // Color of user's primary role, if set
  }
}
```

### User Disconnect

When a user disconnects, all clients receive:

```json
{
  "cmd": "user_disconnect",
  "username": "<username>"
}
```

---

## Heartbeat

The server sends periodic pings to keep the connection alive:

```json
{ "cmd": "ping" }
```

Clients do not need to respond, but should keep the connection open.

---

## Error Packets

All errors are sent as:

```json
{ "cmd": "error", "val": "<error message>", "src": "<command>" }
```

See [Error Handling](errors.md) for details on all possible errors.

---

## Rate Limiting

If a user is rate limited, the server responds:

```json
{ "cmd": "rate_limit", "length": <milliseconds> }
```

- The client should wait the specified time before retrying.

---

## Voice Channel Events

### Voice User Joined

When a user joins a voice channel:

```json
{
  "type": "voice_user_joined",
  "channel": "<channel_name>",
  "user": {
    "id": "<user_id>",
    "username": "<username>",
    "peer_id": "...",     // Only for channel participants
    "muted": false
  },
  "global": true
}
```

### Voice User Left

When a user leaves a voice channel:

```json
{
  "type": "voice_user_left",
  "channel": "<channel_name>",
  "username": "<username>",
  "global": true
}
```

### Voice User Updated

When a user mutes/unmutes:

```json
{
  "type": "voice_user_updated",
  "channel": "<channel_name>",
  "user": {
    "id": "<user_id>",
    "username": "<username>",
    "peer_id": "...",     // Only for channel participants
    "muted": true       // or false
  },
  "global": true
}
```

---

## Global Broadcasting

Some responses include `"global": true`, indicating the message should be broadcast to all connected clients. Examples:
- `message_new` - When a new message is sent
- `message_edit` - When a message is edited
- `message_delete` - When a message is deleted
- `typing` - When a user starts typing
- `message_react_add/remove` - When reactions are added/removed
- Voice events (see above)

Clients should display these messages to all relevant users based on channel permissions.

---

## General Notes

- All packets have a `cmd` field indicating the command type.
- Most responses include a `val` or other data field.
- Text and voice events use different formats (voice uses `type` not `cmd`)
- See also the [commands documentation](./commands/) for all supported commands.

---

**For more details, see:**

- [`handlers/message.py`](../handlers/message.py)
- [`handlers/auth.py`](../handlers/auth.py)
- [`server.py`](../server.py)
- [`handlers/websocket_utils.py`](../handlers/websocket_utils.py)

