# Server Slash Command: /role

Add or remove a role from a user.

## Command

```
/role <action> <username> <role>
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| action | enum | Yes | `add` or `remove` |
| username | string | Yes | The target user |
| role | string | Yes | The role to add or remove |

## Required Roles

- `owner`

## Description

Manage user roles. The `add` action assigns a role to a user, while `remove` removes it.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "✅ Role **moderator** added to **username**.",
        "interaction": {
            "command": "role",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Errors

- `User 'username' not found` - The specified user doesn't exist
- `Role 'role' does not exist` - The role doesn't exist
- `Cannot remove the 'user' role` - Cannot remove base role
- `Cannot remove the user's last role` - Must have at least one role
- `Only the owner can assign the owner role` - Permission restriction
- `Access denied: 'owner' role required` - User lacks required role

## Notes

- The `owner` role can only be assigned by existing owners
- Users must always have at least one role
- The `user` role cannot be removed

## See Also

- [/nick](slash_nick.md) - Set a nickname
