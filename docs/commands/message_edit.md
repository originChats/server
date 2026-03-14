# Command: message_edit

**Request:**

```json
{
  "cmd": "message_edit",
  "id": "<message_id>",
  "channel": "<channel_name>",
  "content": "<new_content>"
}
```

Or for thread messages:

```json
{
  "cmd": "message_edit",
  "id": "<message_id>",
  "thread_id": "<thread_id>",
  "content": "<new_content>"
}
```

- `id`: ID of the message to edit.
- `channel`: Channel name (required if not using `thread_id`).
- `thread_id`: Thread ID (required if not using `channel`).
- `content`: New message content.

**Response:**

- On success:

```json
{
  "cmd": "message_edit",
  "id": "<message_id>",
  "content": "<new_content>",
  "channel": "<channel_name>",
  "global": true
}
```

For thread messages:

```json
{
  "cmd": "message_edit",
  "id": "<message_id>",
  "content": "<new_content>",
  "channel": "<channel_name>",
  "thread_id": "<thread_id>",
  "global": true
}
```

- On error: see [common errors](errors.md).

**Notes:**

- User must be authenticated.
- Rate limiting is enforced.
- Only the original sender can edit their own messages.
- The channel parameter is used for permission checking on thread messages.
- Cannot edit messages in locked or archived threads.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "message_edit":`).
