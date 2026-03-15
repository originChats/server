# Server Slash Command: /nick

Set or clear your display nickname.

## Command

```
/nick [nickname]
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| nickname | string | No | Your new nickname (omit to clear) |

## Required Roles

- None (all authenticated users)

## Description

Set a custom display nickname that appears instead of your username. Call without arguments to clear your nickname.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "Nickname set to **CoolName**",
        "interaction": {
            "command": "nick",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Broadcasts

### nickname_update
When a nickname is set, all clients receive:

```json
{
    "cmd": "nickname_update",
    "user": "USR:abc123",
    "username": "original_name",
    "nickname": "CoolName"
}
```

### nickname_remove
When a nickname is cleared, all clients receive:

```json
{
    "cmd": "nickname_remove",
    "user": "USR:abc123",
    "username": "original_name"
}
```

## Errors

- `Nickname too long (max 20 characters)` - Exceeds length limit

## Notes

- Maximum nickname length is 20 characters
- Nicknames are stored per-user in the database
- Other users see your nickname instead of your username
- Your original username is always preserved

## See Also

- [nickname_update](nickname_update.md) - Event broadcast
- [nickname_remove](nickname_remove.md) - Event broadcast
