# Command: messages_get

Retrieve messages from a text channel.

## Request

```json
{
  "cmd": "messages_get",
  "channel": "<channel_name>",
  "start": <optional_start>,
  "limit": <optional_limit>
}
```

### Fields

- `channel`: (required) Name of the text channel to retrieve messages from.
- `start`: (optional) Starting point for fetching messages.
  - If **integer**: Skips this many recent messages from the end (e.g., `start: 0` gets the most recent messages)
  - If **string** (message ID): Gets messages older than the specified message ID
  - Default: `0` (most recent messages)
- `limit`: (optional) Maximum number of messages to retrieve.
  - Minimum: `1`
  - Maximum: `200` (enforced by server)
  - Default: `100`

## Response

### On Success

```json
{
  "cmd": "messages_get",
  "channel": "<channel_name>",
  "messages": [
    {
      "user": "alice",
      "content": "Hello!",
      "timestamp": 1722510000.123,
      "type": "message",
      "pinned": false,
      "id": "b1c2d3e4-5678-90ab-cdef-1234567890ab"
    },
    // ... more messages
  ]
}
```

- **Messages are returned in chronological order** (oldest first)
- User IDs are converted to usernames
- Includes all message properties (content, timestamp, replies, reactions, etc.)

## Usage Examples

### Get Most Recent Messages (Default)

```json
{
  "cmd": "messages_get",
  "channel": "general"
}
// Returns 100 most recent messages
```

### Fetch Older Messages (Pagination)

```json
{
  "cmd": "messages_get",
  "channel": "general",
  "start": "aabbccdd-1122-3344-5566-77889900aabb",
  "limit": 50
}
// Returns up to 50 messages older than the specified message ID
```

### Skip N Most Recent Messages

```json
{
  "cmd": "messages_get",
  "channel": "general",
  "start": 10,
  "limit": 50
}
// Skips the 10 most recent, returns the next 50
```

### Get Small Batch

```json
{
  "cmd": "messages_get",
  "channel": "general",
  "limit": 20
}
// Returns 20 most recent messages
```

## Error Responses

- `{"cmd": "error", "val": "Invalid channel name"}`
- `{"cmd": "error", "val": "Access denied to this channel"}`
- `{"cmd": "error", "val": "User not authenticated"}`

## Notes

- User must be authenticated.
- User must have `view` permission on the channel.
- Only works on **text channels** (not voice channels).
- Returns empty array if channel has no messages.
- Maximum `limit` of 200 is enforced by the server (any higher value will be capped).

## See Also

- [message_get](message_get.md) - Get a specific message by ID
- [message_replies](message_replies.md) - Get replies to a message
- [message_new](message_new.md) - Send a new message

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "messages_get":`).

