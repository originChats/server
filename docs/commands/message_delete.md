# Command: message_delete

**Request:**

```json
{
  "cmd": "message_delete",
  "id": "<message_id>",
  "channel": "<channel_name>"
}
```

Or for thread messages:

```json
{
  "cmd": "message_delete",
  "id": "<message_id>",
  "thread_id": "<thread_id>"
}
```

- `id`: ID of the message to delete.
- `channel`: Channel name (required if not using `thread_id`).
- `thread_id`: Thread ID (required if not using `channel`).

**Response:**

- On success:

```json
{
  "cmd": "message_delete",
  "id": "<message_id>",
  "channel": "<channel_name>",
  "global": true
}
```

For thread messages:

```json
{
  "cmd": "message_delete",
  "id": "<message_id>",
  "channel": "<channel_name>",
  "thread_id": "<thread_id>",
  "global": true
}
```

- On error: see [common errors](errors.md).

**Notes:**

- User must be authenticated.
- Only the original sender or users with delete permission can delete messages.
- Rate limiting is enforced.
- The channel parameter is used for permission checking on thread messages.
- Cannot delete messages in locked or archived threads.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "message_delete":`).
