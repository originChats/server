# Command: unreads_get

Get the read state and unread counts for all channels and threads the user has access to.

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
    },
    "thread/550e8400-e29b-41d4-a716-446655440000": {
      "last_read": "msg_def456",
      "unread_count": 3,
      "total_messages": 20,
      "parent_channel": "general"
    },
    "thread/6ba7b810-9dad-11d1-80b4-00c04fd430c8": {
      "last_read": null,
      "unread_count": 8,
      "total_messages": 8,
      "parent_channel": "announcements"
    }
  }
}
```

### Response Fields

- `unreads`: Object mapping channel names and thread keys to their read state
  - Channel entries use the channel name as the key (e.g. `"general"`)
  - Thread entries use the key format `"thread/<uuid>"` (e.g. `"thread/550e8400-e29b-41d4-a716-446655440000"`)
- `last_read`: The ID of the last message the user has read (or `null` if never read)
- `unread_count`: Number of messages since `last_read`
- `total_messages`: Total number of messages in the channel/thread
- `parent_channel`: (thread entries only) The name of the channel this thread belongs to

## Usage Examples

### Get all unread counts on connect

```javascript
ws.send(JSON.stringify({ cmd: 'unreads_get' }));

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.cmd === 'unreads_get') {
    for (const [key, info] of Object.entries(data.unreads)) {
      if (key.startsWith('thread/')) {
        const threadId = key.slice(7); // remove "thread/" prefix
        console.log(`Thread ${threadId} (${info.parent_channel}): ${info.unread_count} unread`);
      } else {
        console.log(`${key}: ${info.unread_count} unread`);
      }
    }
  }
};
```

### Check if channel or thread has unreads

```javascript
const response = await sendCommand({ cmd: 'unreads_get' });

// Check channel unreads
const generalUnreads = response.unreads['general']?.unread_count ?? 0;
if (generalUnreads > 0) {
  showNotification(`${generalUnreads} unread messages in #general`);
}

// Check thread unreads
for (const [key, info] of Object.entries(response.unreads)) {
  if (key.startsWith('thread/') && info.unread_count > 0) {
    showNotification(`${info.unread_count} unread in thread (${info.parent_channel})`);
  }
}
```

### Group thread unreads by parent channel

```javascript
const response = await sendCommand({ cmd: 'unreads_get' });

const threadsByChannel = {};
for (const [key, info] of Object.entries(response.unreads)) {
  if (key.startsWith('thread/')) {
    const threadId = key.slice(7);
    const channel = info.parent_channel;
    if (!threadsByChannel[channel]) threadsByChannel[channel] = [];
    threadsByChannel[channel].push({ threadId, ...info });
  }
}
```

## Notes

- Only returns channels the user has `view` permission for.
- Thread unreads are only included for threads in channels the user has `view` permission for.
- Voice channels are not included (only text channels).
- The `unread_count` is calculated at query time based on the stored `last_read` position.
- If `last_read` is `null`, the entire channel/thread history is considered unread.
- Thread keys use the format `thread/<uuid>` (e.g. `"thread/550e8400-e29b-41d4-a716-446655440000"`), while channel keys are plain channel names (e.g. `"general"`).

## See Also

- [unreads_ack](unreads_ack.md) - Mark a channel/thread as read
- [unreads_count](unreads_count.md) - Get unread count for a single channel/thread
- [messages_get](messages_get.md) - Auto-acks when fetching messages
- [thread_get](thread_get.md) - Get details about a specific thread
