# Command: users_list

**Request:**
```json
{"cmd": "users_list"}
```

**Response:**
- On success:
```json
{
  "cmd": "users_list",
  "users": [
    {
      "id": "user_id",
      "username": "example_user",
      "nickname": "Display Name",
      "status": {
        "status": "online",
        "text": "Working on something cool"
      },
      "roles": ["role1", "role2"]
    }
  ]
}
```
- On error: see [common errors](errors.md).

**User Object Fields:**
- `id` - The user's unique identifier
- `username` - The user's username
- `nickname` - The user's display nickname (optional, may not be present)
- `status` - Object containing `status` (online/idle/dnd/invisible) and `text` (custom message)
- `roles` - Array of role names assigned to the user

**Notes:**
- User must be authenticated.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "users_list":`).
