# Event: nickname_update

Broadcast when a user sets or updates their nickname.

## Server Broadcast

```json
{
    "cmd": "nickname_update",
    "user": "USR:abc123",
    "username": "original_name",
    "nickname": "Custom Nick"
}
```

### Fields

- `user`: The user ID of the user who changed their nickname
- `username`: The user's original username
- `nickname`: The new nickname that was set

## Description

This event is broadcast to all connected clients when a user uses the `/nick` command to set or update their nickname. The nickname appears alongside or instead of the username in the client UI.

## Notes

- Maximum nickname length is 20 characters
- Use `nickname_update` for initial nickname set or changes
- Use `nickname_remove` when a user clears their nickname

## See Also

- [nickname_remove](nickname_remove.md) - Event when nickname is cleared
- `/nick` command - Set or clear your own nickname
