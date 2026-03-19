# Command: status_set

**Request:**
```json
{
  "cmd": "status_set",
  "status": "online",
  "text": "Working on something cool"
}
```

**Parameters:**
- `status` (required): The status to set. Must be one of: `online`, `idle`, `dnd`, `offline`.
- `text` (optional): A custom status message (max 100 characters).

**Response:**
- On success:
```json
{
  "cmd": "status_set",
  "status": {
    "status": "online",
    "text": "Working on something cool"
  }
}
```
- On error: see [common errors](../errors.md).

**Broadcast:**
When a user's status is changed, a `status_get` event is broadcast to all connected clients:
```json
{
  "cmd": "status_get",
  "username": "example_user",
  "status": {
    "status": "online",
    "text": "Working on something cool"
  }
}
```

**Offline Status Behavior:**
- When a user sets their status to `offline`, a `user_disconnect` event is broadcast to make them appear offline
- The user still remains connected and can receive messages
- Status broadcasts are suppressed while offline
- When switching from `offline` to any other status, a `user_connect` event is broadcast followed by the `status_get` event

**Notes:**
- User must be authenticated.
- Valid status values: `online`, `idle`, `dnd`, `invisible`.
- `text` is optional and limited to 100 characters.

See implementation: [`handlers/messages/status.py`](../../handlers/messages/status.py).
