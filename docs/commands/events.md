# Server Events

This page documents server-side events that are automatically broadcast to clients without a client request.

## slash_add

Automatically broadcast to all connected clients when new slash commands are registered via `slash_register`.

### Event Data

```json
{
  "cmd": "slash_add",
  "commands": [
    {
      "name": "command_name",
      "description": "Command description",
      "options": [
        {
          "name": "option_name",
          "description": "Option description",
          "type": "str|int|float|bool|enum",
          "required": true,
          "choices": ["choice1", "choice2"]
        }
      ],
      "whitelistRoles": ["role1", "role2"],
      "blacklistRoles": ["role3"],
      "ephemeral": false,
      "registeredBy": "username"
    }
  ]
}
```

### Fields

- `commands`: Array of command objects that were registered
  - `name`: Command name (without `/` prefix)
  - `description`: Description of what the command does
  - `options`: Array of command options/arguments
  - `whitelistRoles`: Roles allowed to use this command (null/undefined if all roles)
  - `blacklistRoles`: Roles NOT allowed to use this command
  - `ephemeral`: Whether the command response is ephemeral
  - `registeredBy`: Username of the user who registered this command

### Behavior

- Broadcast to all authenticated connected clients
- Sent immediately after successful `slash_register`
- Contains all commands that were just registered (not all commands on the server)

### Handling

Clients should:
1. Listen for `slash_add` events
2. Add the received commands to their local command registry
3. Update UI to reflect available commands
4. Ensure commands are associated with the `registeredBy` user for proper display

### Example

When a user registers the `/ping` command:

```javascript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'slash_add') {
    data.commands.forEach(cmd => {
      addCommandToRegistry(cmd);
      console.log(`Command /${cmd.name} registered by ${cmd.registeredBy}`);
    });
  }
};
```

## slash_remove

Automatically broadcast to all connected clients when slash commands are removed (typically when the connection that registered them disconnects).

### Event Data

```json
{
  "cmd": "slash_remove",
  "commands": ["command_name1", "command_name2", ...]
}
```

### Fields

- `commands`: Array of command names that were removed

### Behavior

- Broadcast to all authenticated connected clients
- Sent when a WebSocket connection disconnects that had registered slash commands
- Contains names of commands that should be removed from client registries

### Handling

Clients should:
1. Listen for `slash_remove` events
2. Remove the specified commands from their local command registry
3. Update UI to reflect removed commands

### Example

When a connection with registered commands disconnects:

```javascript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'slash_remove') {
    data.commands.forEach(cmdName => {
      removeCommandFromRegistry(cmdName);
      console.log(`Command /${cmdName} removed`);
    });
  }
};
```

## Event Lifecycle

```
[slash_register request]
       ↓
   [Validate commands]
       ↓
   [Store in server]
       ↓
   [Broadcast slash_add]
       ↓
   [Clients add commands]
       ↓
[User disconnects]
       ↓
   [Remove from server]
       ↓
   [Broadcast slash_remove]
       ↓
   [Clients remove commands]
```

## Best Practices for Client Handling

1. **Debounce updates**: When receiving multiple events in rapid succession, debounce UI updates
2. **Handle duplicates**: Check if a command already exists before adding (though the server should prevent duplicates)
3. **Validate commands**: Ensure received commands have all required fields
4. **Handle unknown commands**: Log warnings if a `slash_remove` references an unknown command
5. **Sync with slash_list**: Periodically call `slash_list` to verify local state matches server state

See implementation details:
- [slash_register](slash_register.md) - Command registration
- [slash_list](slash_list.md) - List all commands
- handlers/message.py - Event broadcasting logic
- server.py - Disconnect handling
