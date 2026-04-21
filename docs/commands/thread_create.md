# thread_create

Create a new thread in a forum channel.

## Request

```json
{
    "cmd": "thread_create",
    "channel": "announcements",
    "name": "Welcome to the server!"
}
```

### Parameters

| Parameter | Type   | Required | Description                           |
|-----------|--------|----------|---------------------------------------|
| `channel` | string | Yes      | The forum channel to create thread in |
| `name`    | string | Yes      | The name/title of the thread          |

## Response

### Success

```json
{
    "cmd": "thread_create",
    "thread": {
        "id": "uuid-here",
        "name": "Welcome to the server!",
        "parent_channel": "announcements",
        "created_by": "alice",
        "created_at": 1234567890.123,
        "locked": false,
        "archived": false,
        "last_message": null,
        "last_message_id": null
    },
    "channel": "announcements",
    "global": true
}
```

### Error Responses

| Error Message                                    | Cause                                    |
|--------------------------------------------------|------------------------------------------|
| `"Channel and thread name are required"`         | Missing channel or name parameter        |
| `"User roles not found"`                         | User has no roles                        |
| `"Channel not found"`                            | Channel doesn't exist                    |
| `"Threads can only be created in forum channels"`| Channel is not a forum type              |
| `"You do not have permission..."`                | Missing `create_thread` permission       |
| `"Thread name cannot be empty"`                  | Empty thread name after stripping        |

## Permissions

Requires `create_thread` permission in the forum channel.

## Related

- [thread_get](thread_get.md) - Get thread details
- [thread_messages](thread_messages.md) - Get thread messages
- [thread_delete](thread_delete.md) - Delete a thread
- [thread_update](thread_update.md) - Update thread properties
