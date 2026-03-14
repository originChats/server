# Command: message_react_add

**Request:**
```json
{
  "cmd": "message_react_add",
  "channel": "<channel_name>",
  "id": "<message_id>",
  "emoji": "<emoji>"
}
```

Or for thread messages:

```json
{
  "cmd": "message_react_add",
  "thread_id": "<thread_id>",
  "id": "<message_id>",
  "emoji": "<emoji>"
}
```

- `channel`: Channel name (required if not using `thread_id`).
- `thread_id`: Thread ID (required if not using `channel`).
- `id`: Message ID.
- `emoji`: Emoji to add.

**Response:**
- On success:
```json
{
  "cmd": "message_react_add",
  "id": "<message_id>",
  "channel": "<channel_name>",
  "emoji": "<emoji>",
  "from": "<username>"
}
```

For thread messages:
```json
{
  "cmd": "message_react_add",
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
- User must have permission to add reactions to the message.
- Cannot react to messages in locked or archived threads.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "message_react_add":`).
