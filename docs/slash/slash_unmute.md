# Server Slash Command: /unmute

Remove a mute from a user.

## Command

```
/unmute <username>
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| username | string | Yes | The user to unmute |

## Required Roles

- `admin` or `owner`

## Description

Removes an active mute/timeout from a user, allowing them to send messages again immediately.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "🔊 **username** has been unmuted.",
        "interaction": {
            "command": "unmute",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Errors

- `User 'username' not found` - The specified user doesn't exist
- `Access denied: 'admin' role required` - User lacks required role

## See Also

- [/mute](slash_mute.md) - Mute a user
