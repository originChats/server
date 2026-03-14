# Command: message_get

**Request:**
```json
{
  "cmd": "message_get",
  "channel": "<channel_name>",
  "id": "<message_id>"
}
```

Or for thread messages:

```json
{
  "cmd": "message_get",
  "thread_id": "<thread_id>",
  "id": "<message_id>"
}
```

- `channel`: Channel name (required if not using `thread_id`).
- `thread_id`: Thread ID (required if not using `channel`).
- `id`: Message ID.

**Response:**
- On success:
```json
{
  "cmd": "message_get",
  "channel": "<channel_name>",
  "message": { ...message object... }
}
```

For thread messages:
```json
{
  "cmd": "message_get",
  "channel": "<channel_name>",
  "thread_id": "<thread_id>",
  "message": { ...message object... }
}
```

The message object also contains "position" which tells you where in the channel/thread the message is

- On error: see [common errors](errors.md).

**Notes:**
- User must be authenticated and have access to the channel/thread.
- Cannot access messages in locked or archived threads.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "message_get":`).
