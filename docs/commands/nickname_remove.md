# Event: nickname_remove

Broadcast when a user clears their nickname.

## Server Broadcast

```json
{
    "cmd": "nickname_remove",
    "user": "USR:abc123",
    "username": "original_name"
}
```

### Fields

- `user`: The user ID of the user who removed their nickname
- `username`: The user's original username

## Description

This event is broadcast to all connected clients when a user clears their nickname using the `/nick` command without arguments. Clients should display the original username after receiving this event.

## Notes

- This event is sent when `/nick` is called without arguments and the user has an existing nickname
- After this event, the user has no nickname set

## See Also

- [nickname_update](nickname_update.md) - Event when nickname is set
- `/nick` command - Set or clear your own nickname
