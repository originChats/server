# Server Slash Command: /mute

Temporarily mute (timeout) a user.

## Command

```
/mute <username> <duration> [reason]
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| username | string | Yes | The user to mute |
| duration | integer | Yes | Duration in seconds |
| reason | string | No | Reason for the mute |

## Required Roles

- `admin` or `owner`

## Description

Temporarily prevents a user from sending messages. The user will receive a rate limit notification and cannot send messages until the duration expires.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "🔇 **username** has been muted for 60 seconds.\n**Reason:** Spam",
        "interaction": {
            "command": "mute",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Errors

- `User 'username' not found` - The specified user doesn't exist
- `Cannot mute the server owner` - Attempting to mute the owner
- `Duration must be a positive number` - Invalid duration
- `Access denied: 'admin' role required` - User lacks required role

## Notes

- The muted user receives a `rate_limit` packet with the mute reason
- Use `/unmute` to remove the mute early

## See Also

- [/unmute](slash_unmute.md) - Remove a mute
- [/ban](slash_ban.md) - Permanently ban a user
