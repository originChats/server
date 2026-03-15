# Server Slash Command: /ban

Ban a user from the server.

## Command

```
/ban <username> [reason]
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| username | string | Yes | The user to ban |
| reason | string | No | Reason for the ban |

## Required Roles

- `admin` or `owner`

## Description

Bans the specified user from the server. A banned user cannot reconnect to the server. The ban is persistent across server restarts.

## Response

When successful, the command creates a message in the channel with the ban confirmation:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "🚫 **username** has been banned.\n**Reason:** reason",
        "interaction": {
            "command": "ban",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Errors

- `User 'username' not found` - The specified user doesn't exist
- `Cannot ban the server owner` - Attempting to ban the owner
- `Access denied: 'admin' role required` - User lacks required role
- `Username is required` - Missing required parameter

## Notes

- Banned users are stored in the database and persist across restarts
- The `user_ban` plugin event is triggered when a user is banned
- Use `/unban` to reverse this action

## See Also

- [/unban](slash_unban.md) - Unban a user
- [/mute](slash_mute.md) - Temporarily mute a user
