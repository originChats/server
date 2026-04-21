# thread_get

Get details about a specific thread.

## Request

```json
{
    "cmd": "thread_get",
    "thread_id": "uuid-here"
}
```

### Parameters

| Parameter   | Type   | Required | Description          |
|-------------|--------|----------|----------------------|
| `thread_id` | string | Yes      | The thread ID to get |

## Response

### Success

```json
{
    "cmd": "thread_get",
    "thread": {
        "id": "uuid-here",
        "name": "Welcome to the server!",
        "parent_channel": "announcements",
        "created_by": "alice",
        "created_at": 1234567890.123,
        "locked": false,
        "archived": false,
        "last_message": 1234567900.456,
        "last_message_id": "msg_uuid_here"
    }
}
```

### Error Responses

| Error Message                      | Cause                         |
|------------------------------------|-------------------------------|
| `"Thread ID is required"`          | Missing thread_id parameter   |
| `"Thread not found"`               | Thread doesn't exist          |
| `"User roles not found"`           | User has no roles             |
| `"You do not have permission..."`  | Missing view permission       |

## Permissions

Requires `view` permission in the parent channel.

## Related

- [thread_create](thread_create.md) - Create a new thread
- [thread_messages](thread_messages.md) - Get thread messages
