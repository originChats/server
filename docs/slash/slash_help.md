# Server Slash Command: /help

List all available slash commands.

## Command

```
/help
```

## Parameters

None

## Required Roles

- None (all authenticated users)

## Description

Lists all slash commands available to the current user. Only shows commands the user has permission to use based on their roles.

## Response

When successful, the command creates a message in the channel:

```json
{
    "cmd": "message_new",
    "message": {
        "user": "originChats",
        "content": "**Available Commands:**\n• `/ban` - Ban a user from the server\n• `/help` - List all available slash commands\n• `/nick` - Set or clear your display nickname",
        "interaction": {
            "command": "help",
            "username": "invoker_name"
        }
    },
    "channel": "general",
    "global": true
}
```

## Notes

- Command list is filtered based on user roles
- Shows both server commands and client-registered commands
- Commands are sorted alphabetically

## See Also

All other slash commands
