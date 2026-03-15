# Server Slash Command: /channel

Create or delete a channel.

## Command

```
/channel <action> <name> [type]
```

## Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| action | enum | Yes | `create` or `delete` |
| name | string | Yes | The channel name |
| type | enum | No | `text` or `voice` (default: `text`) - only for create |

## Required Roles

- `owner`

## Description

Manage server channels. Create new text or voice channels, or delete existing ones.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "✅ Channel **#new-channel** (text) created.",
        "interaction": {
            "command": "channel",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Errors

- `Channel 'name' already exists` - Channel name taken (create)
- `Channel 'name' not found` - Channel doesn't exist (delete)
- `Channel type must be 'text' or 'voice'` - Invalid type
- `Cannot delete the channel you are currently in` - Voice channel restriction
- `Access denied: 'owner' role required` - User lacks required role

## Notes

- Channel names should be unique
- Deleting a channel removes all its messages

## See Also

- [/role](slash_role.md) - Manage user roles
