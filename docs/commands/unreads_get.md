# Command: unreads_get

Get the read state and unread counts for all channels the user has access to.

## Request

```json
{
  "cmd": "unreads_get"
}
```

No parameters required.

## Response

### On Success

```json
{
  "cmd": "unreads_get",
  "unreads": {
    "general": {
      "last_read": "msg_abc123",
      "unread_count": 5,
      "total_messages": 100
    },
    "random": {
      "last_read": null,
      "unread_count": 50,
      "total_messages": 50
    },
    "announcements": {
      "last_read": "msg_xyz789",
      "unread_count": 0,
      "total_messages": 25
    }
  }
}
```

### Response Fields

- `unreads`: Object mapping channel names to their read state
  - `last_read`: The ID of the last message the user has read (or `null` if never read)
  - `unread_count`: Number of messages since `last_read`
  - `total_messages`: Total number of messages in the channel

## Usage Examples

### Get all unread counts on connect

```javascript
ws.send(JSON.stringify({ cmd: 'unreads_get' }));

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.cmd === 'unreads_get') {
    for (const [channel, info] of Object.entries(data.unreads)) {
      console.log(`${channel}: ${info.unread_count} unread`);
    }
  }
};
```

### Check if channel has unreads

```javascript
const response = await sendCommand({ cmd: 'unreads_get' });
const generalUnreads = response.unreads['general']?.unread_count ?? 0;

if (generalUnreads > 0) {
  showNotification(`${generalUnreads} unread messages in #general`);
}
```

## Notes

- Only returns channels the user has `view` permission for.
- Voice channels are not included (only text channels).
- The `unread_count` is calculated at query time based on the stored `last_read` position.
- If `last_read` is `null`, the entire channel history is considered unread.
- This does **not** include thread unreads - use `unreads_count` with `thread_id` for threads.

## See Also

- [unreads_ack](unreads_ack.md) - Mark a channel/thread as read
- [unreads_count](unreads_count.md) - Get unread count for a single channel/thread
- [messages_get](messages_get.md) - Auto-acks when fetching messages
