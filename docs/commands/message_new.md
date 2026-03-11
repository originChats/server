# Command: message_new

**Request:**
```json
{
  "cmd": "message_new",
  "channel": "<channel_name>",
  "content": "<message_content>",
  "reply_to": "<optional_message_id>",
  "ping": true
}
```

### Fields

- `channel`: Name of the channel to send the message to.
- `content`: Message text (required, trimmed, max length enforced by config).
- `reply_to`: (Optional) ID of the message being replied to.
- `ping`: (Optional) Whether to notify the user being replied to. Defaults to `true`. Only applies when using `reply_to`.

**Response:**
- On success:
```json
{
  "cmd": "message_new",
  "message": {
    "id": "message-uuid",
    "user": "username",
    "content": "Message content here",
    "timestamp": 1773182676.073865,
    "type": "message",
    "pinned": false,
    "reply_to": {
      "id": "original-message-id",
      "user": "original-username"
    },
    "ping": true
  },
  "channel": "<channel_name>",
  "global": true
}
```

- On error: see [common errors](errors.md).

**Notes:**
- User must be authenticated and have permission to send in the channel.
- Rate limiting and message length are enforced.
- Replies include a `reply_to` field in the message object.
- The `ping` field controls whether a reply counts as a ping to the original message author:
  - If `ping` is `true` or not provided (default): The reply will be included in `pings_get` for the user being replied to
  - If `ping` is `false`: The reply will NOT be included in `pings_get` for the user being replied to
  - This allows users to reply without notifying/pinging the original poster
- The `ping` field is only included in the response if explicitly provided in the request; it defaults to `true` for `pings_get` lookups

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "message_new":`).
