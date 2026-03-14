
# Command: message_react_remove

**Request:**
```json
{
  "cmd": "message_react_remove",
  "channel": "<channel_name>",
  "id": "<message_id>",
  "emoji": "<emoji>"
}
```

Or for thread messages:

```json
{
  "cmd": "message_react_remove",
  "thread_id": "<thread_id>",
  "id": "<message_id>",
  "emoji": "<emoji>"
}
```

- `channel`: Channel name (required if not using `thread_id`).
- `thread_id`: Thread ID (required if not using `channel`).
- `id`: Message ID.
- `emoji`: Emoji to remove.

**Response:**
- On success:
```json
{
  "cmd": "message_react_remove",
  "id": "<message_id>",
  "channel": "<channel_name>",
  "emoji": "<emoji>",
  "from": "<username>"
}
```

For thread messages:
```json
{
  "cmd": "message_react_remove",
  "id": "<message_id>",
  "channel": "<channel_name>",
  "thread_id": "<thread_id>",
  "emoji": "<emoji>",
  "from": "<username>"
}
```

- On error: see [common errors](errors.md).

**Notes:**
- User must be authenticated and have access to the channel/thread.
- User must have permission to remove reactions from the message.
- Cannot remove reactions from messages in locked or archived threads.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "message_react_remove":`).
