# Command: unreads_count

Get the unread count and read state for a single channel or thread.

## Request

### For a channel

```json
{
  "cmd": "unreads_count",
  "channel": "<channel_name>"
}
```

### For a thread

```json
{
  "cmd": "unreads_count",
  "thread_id": "<thread_id>"
}
```

### Fields

- `channel`: (required if not using `thread_id`) Name of the channel to check.
- `thread_id`: (required if not using `channel`) ID of the thread to check.

## Response

### On Success (Channel)

```json
{
  "cmd": "unreads_count",
  "channel": "general",
  "unread_count": 5,
  "last_read": "msg_abc123",
  "total_messages": 100
}
```

### On Success (Thread)

```json
{
  "cmd": "unreads_count",
  "thread_id": "thread-12345",
  "unread_count": 12,
  "last_read": "msg_xyz789",
  "total_messages": 50
}
```

### Response Fields

- `unread_count`: Number of messages since `last_read`
- `last_read`: The ID of the last message the user has read (or `null` if never read)
- `total_messages`: Total number of messages in the channel/thread

## Usage Examples

### Check unread count for a channel

```javascript
ws.send(JSON.stringify({
  cmd: 'unreads_count',
  channel: 'general'
}));
```

### Check unread count for a thread

```javascript
ws.send(JSON.stringify({
  cmd: 'unreads_count',
  thread_id: 'thread-12345'
}));
```

### Display unread badge

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.cmd === 'unreads_count') {
    if (data.unread_count > 0) {
      showBadge(data.unread_count);
    } else {
      hideBadge();
    }
  }
};
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
- If `last_read` is `null`, all messages are considered unread.
- Use `unreads_get` to get unread counts for all channels at once.

## See Also

- [unreads_ack](unreads_ack.md) - Mark a channel/thread as read
- [unreads_get](unreads_get.md) - Get unread counts for all channels
- [messages_get](messages_get.md) - Auto-acks when fetching messages
