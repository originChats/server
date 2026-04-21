# thread_update

Update thread properties like name, locked, or archived status.

## Request

```json
{
    "cmd": "thread_update",
    "thread_id": "uuid-here",
    "name": "New Thread Title",
    "archived": true,
    "last_message": 1234567900.456,
    "last_message_id": "msg_uuid_here"
}
```

### Parameters

| Parameter   | Type    | Required | Description                              |
|-------------|---------|----------|------------------------------------------|
| `thread_id` | string  | Yes      | The thread ID to update                  |
| `name`      | string  | No       | New thread title                         |
| `locked`    | boolean | No       | Lock/unlock thread (admin/owner only)    |
| `archived`  | boolean | No       | Archive/unarchive thread                 |

## Response

### Success

```json
{
    "cmd": "thread_update",
    "thread": {
        "id": "uuid-here",
        "name": "New Thread Title",
        "parent_channel": "announcements",
        "created_by": "alice",
        "created_at": 1234567890.123,
        "locked": false,
        "archived": true
    },
    "global": true
}
```

### Error Responses

| Error Message                     | Cause                        |
|-----------------------------------|------------------------------|
| `"Thread ID is required"`         | Missing thread_id parameter  |
| `"Thread not found"`              | Thread doesn't exist         |
| `"User roles not found"`          | User has no roles            |
| `"You do not have permission..."` | Not creator/admin/owner      |
| `"Thread name cannot be empty"`   | Empty name after stripping   |

## Permissions

- Thread creator can update name and archived status
- Admins and owners can additionally update locked status

## Related

- [thread_create](thread_create.md) - Create a new thread
- [thread_delete](thread_delete.md) - Delete a thread
