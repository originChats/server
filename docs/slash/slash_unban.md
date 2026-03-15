# Server Slash Command: /unban

Unban a user from the server.

## Command

```
/unban <username>
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| username | string | Yes | The user to unban |

## Required Roles

- `admin` or `owner`

## Description

Removes the ban from a previously banned user, allowing them to reconnect to the server.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "✅ **username** has been unbanned.",
        "interaction": {
            "command": "unban",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Errors

- `User 'username' not found` - The specified user doesn't exist
- `User 'username' is not banned` - The user is not currently banned
- `Access denied: 'admin' role required` - User lacks required role

## See Also

- [/ban](slash_ban.md) - Ban a user
