# Command: unreads_ack

Mark a channel or thread as read up to a specific message (or the latest message).

## Request

### Mark channel as read (up to latest)

```json
{
  "cmd": "unreads_ack",
  "channel": "<channel_name>"
}
```

### Mark channel as read (up to specific message)

```json
{
  "cmd": "unreads_ack",
  "channel": "<channel_name>",
  "message_id": "<message_id>"
}
```

### Mark thread as read (up to latest)

```json
{
  "cmd": "unreads_ack",
  "thread_id": "<thread_id>"
}
```

### Mark thread as read (up to specific message)

```json
{
  "cmd": "unreads_ack",
  "thread_id": "<thread_id>",
  "message_id": "<message_id>"
}
```

### Fields

- `channel`: (required if not using `thread_id`) Name of the channel to mark as read.
- `thread_id`: (required if not using `channel`) ID of the thread to mark as read.
- `message_id`: (optional) The message ID to mark as the last read position. If omitted, marks up to the latest message.

## Response

### On Success (Channel)

```json
{
  "cmd": "unreads_ack",
  "channel": "general",
  "last_read": "msg_abc123"
}
```

### On Success (Thread)

```json
{
  "cmd": "unreads_ack",
  "thread_id": "thread-12345",
  "last_read": "msg_xyz789"
}
```

## Side Effects

When `unreads_ack` is called:

1. The user's read position is updated in the database
2. An `unreads_update` event is broadcast to **all connections** for that user

```json
{
  "cmd": "unreads_update",
  "channel": "general",
  "last_read": "msg_abc123"
}
```

This allows multiple devices/connections to stay in sync.

## Usage Examples

### Mark channel as fully read

```javascript
ws.send(JSON.stringify({
  cmd: 'unreads_ack',
  channel: 'general'
}));
```

### Mark thread as fully read

```javascript
ws.send(JSON.stringify({
  cmd: 'unreads_ack',
  thread_id: 'thread-12345'
}));
```

### Mark as read up to a specific message

```javascript
ws.send(JSON.stringify({
  cmd: 'unreads_ack',
  channel: 'general',
  message_id: 'msg_abc123'
}));
```

## Error Responses

- `{"cmd": "error", "val": "Channel or thread_id is required"}`
- `{"cmd": "error", "val": "Channel not found"}`
- `{"cmd": "error", "val": "Thread not found"}`
- `{"cmd": "error", "val": "Access denied to this channel"}`
- `{"cmd": "error", "val": "Authentication required"}`

## Notes

- User must be authenticated.
- User must have `view` permission on the channel/thread.
- The `message_id` parameter is optional - if not provided, the latest message is used.
- This command is also implicitly called by `messages_get` (auto-ack).
- Read state persists across sessions and devices.

## See Also

- [unreads_get](unreads_get.md) - Get all unread states
- [unreads_count](unreads_count.md) - Get unread count for a single channel/thread
- [messages_get](messages_get.md) - Auto-acks when fetching messages
