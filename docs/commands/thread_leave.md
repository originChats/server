# thread_leave

Leave a thread in a forum channel.

## Request

```json
{
  "cmd": "thread_leave",
  "thread_id": "uuid-here"
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|--------|----------|-------------------------|
| `thread_id` | string | Yes | The ID of the thread to leave |

## Response

### Success

```json
{
  "cmd": "thread_leave",
  "thread": {
    "id": "uuid-here",
    "name": "Welcome to the server!",
    "parent_channel": "announcements",
    "created_by": "alice",
    "created_at": 1234567890.123,
    "locked": false,
    "archived": false,
    "participants": ["alice"],
    "last_message": 1234567900.456,
    "last_message_id": "msg_uuid_here"
  },
  "thread_id": "uuid-here",
  "user": "bob",
  "global": true
}
```

### Error Responses

| Error Message | Cause |
|--------------------------------------------------|------------------------------------------|
| `"Authentication required"` | User not authenticated |
| `"Thread ID is required"` | Missing thread_id parameter |
| `"Thread not found"` | Thread doesn't exist |

## Permissions

No specific permissions required.

## Related

- [thread_join](thread_join.md) - Join a thread
- [thread_get](thread_get.md) - Get thread details
- [thread_create](thread_create.md) - Create a new thread
