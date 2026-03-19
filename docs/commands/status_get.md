# Command: status_get

**Request:**
```json
{
  "cmd": "status_get",
  "user": "target_username"
}
```

**Parameters:**
- `user` (required): The username or user ID to get the status for.

**Response:**
- On success:
```json
{
  "cmd": "status_get",
  "username": "target_username",
  "status": {
    "status": "online",
    "text": "Working on something cool"
  }
}
```
- On error: see [common errors](../errors.md).

**Notes:**
- User must be authenticated.
- The `user` parameter can be either a username or a user ID.
- Returns the target user's current status object with `status` and `text` fields.

See implementation: [`handlers/messages/status.py`](../../handlers/messages/status.py).
