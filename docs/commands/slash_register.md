# Command: slash_register

Register new slash commands (owner only, per connection).

## Request

```json
{
  "cmd": "slash_register",
  "commands": [  // Array of slash command objects
    {
      "name": "help",
      "description": "Get help information",
      "options": [
        {
          "name": "topic",
          "description": "Topic to get help for",
          "type": "str",
          "required": false
        }
      ],
      "whitelistRoles": ["user", "moderator"],
      "blacklistRoles": null,
      "ephemeral": false
    },
    // ... more commands
  ]
}
```

### Fields

- `commands`: (required) Array of slash command objects to register.

### Slash Command Object Fields

- `name`: (required) Command name (without `/` prefix, e.g., "help")
- `description`: (required) Description of what the command does
- `options`: (optional, default: `[]`) Array of command options/arguments
  - `name`: Option name
  - `description`: Description of the option
  - `type`: Data type - `"str"`, `"int"`, `"float"`, `"bool"`, or `"enum"`
  - `required`: Whether the option is required (default: `true`)
  - `choices`: If type is `"enum"`, array of valid choices (required for enum)
- `whitelistRoles`: (optional) Array of role names allowed to use this command. If omitted or null, all roles can use it.
- `blacklistRoles`: (optional) Array of role names NOT allowed to use this command. Takes precedence over whitelist.
- `ephemeral`: (optional, default: `false`) Whether the command response is ephemeral (only visible to the caller)

## Response

### On Success

```json
{
  "cmd": "slash_register",
  "val": "2 commands registered successfully"
}
```

The response is sent only to the registering user. All connected clients automatically receive a `slash_add` event.

### Server Broadcast (slash_add)

When commands are successfully registered, the server automatically broadcasts to all connected clients:

```json
{
  "cmd": "slash_add",
  "commands": [
    {
      "name": "help",
      "description": "Get help information",
      "options": [...],
      "whitelistRoles": ["user", "moderator"],
      "blacklistRoles": null,
      "ephemeral": false,
      "registeredBy": "username"
    }
  ]
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Commands must be provided as a list"}`
- `{"cmd": "error", "val": "No server data provided"}`
- `{"cmd": "error", "val": "Invalid command schema: ..."}` - When validation fails
- `{"cmd": "error", "val": "You already have slash commands registered from another session"}` - When user tries to register from multiple connections

## Notes

- Requires `owner` role.
- Commands are registered **per WebSocket connection** - each connection can have its own set of commands.
- **Only one connection per user can have commands registered**. If a user tries to register commands from a second connection, they will receive an error.
- Can register multiple commands in a single request.
- Commands are validated against the SlashCommand schema.
- If a command with the same name already exists, it will be overwritten.
- When new commands are registered, a `slash_add` event is automatically broadcast to all connected clients.
- When the connection that registered commands disconnects, all those commands are automatically removed with a `slash_remove` broadcast.
- Options support type validation and required fields.
- `whitelistRoles` and `blacklistRoles` control who can use the command (role-based access).
- `ephemeral` commands (in slash_call) send responses only to the caller.

## Slash Command Lifecycle

1. Register via `slash_register` command (per connection)
2. Server broadcasts `slash_add` to all clients
3. User calls it via `slash_call` command (can be called by any user if they have permissions)
4. Server validates inputs based on schema
5. Server executes callback or plugin handler
6. Response is sent back
7. When the registering connection disconnects, commands are automatically removed with `slash_remove` broadcast

## Automatic Synchronization

### When commands are registered:
- The registering user receives a success response
- All connected clients receive a `slash_add` event containing the new commands
- Each command includes the `registeredBy` field with the username of the user who registered it

### When the connection disconnects:
- All commands registered by that connection are automatically removed
- A `slash_remove` event is broadcast to all connected clients:
  ```json
  {
    "cmd": "slash_remove",
    "commands": ["command1", "command2", ...]
  }
  ```

### Multiple connections prevention:
- If a user already has commands registered from one connection and tries to register commands from another connection, they will receive an error
- This prevents duplicate command registration from multiple sessions

## Usage Examples

### Simple Command

```json
{
  "cmd": "slash_register",
  "commands": [
    {
      "name": "ping",
      "description": "Check if the server is responding",
      "options": [],
      "ephemeral": false
    }
  ]
}
```

### Command with Required Options

```json
{
  "cmd": "slash_register",
  "commands": [
    {
      "name": "weather",
      "description": "Get weather for a city",
      "options": [
        {
          "name": "city",
          "description": "City name",
          "type": "str",
          "required": true
        }
      ]
    }
  ]
}
```

### Command with Enum Options

```json
{
  "cmd": "slash_register",
  "commands": [
    {
      "name": "mood",
      "description": "Set your mood",
      "options": [
        {
          "name": "mood",
          "description": "Your current mood",
          "type": "enum",
          "choices": ["happy", "sad", "excited", "tired"],
          "required": true
        }
      ],
      "ephemeral": true
    }
  ]
}
```

### Role-Restricted Command

```json
{
  "cmd": "slash_register",
  "commands": [
    {
      "name": "purge",
      "description": "Purge messages (admin only)",
      "options": [
        {
          "name": "count",
          "description": "Number of messages to purge",
          "type": "int",
          "required": true
        }
      ],
      "whitelistRoles": ["admin"]
    }
  ]
}
```

## See Also

- [slash_list](slash_list.md) - List all registered slash commands from all connections
- [slash_call](slash_call.md) - Execute a slash command
- [slash_response](slash_response.md) - Response format from slash commands
- [slash_add](events.md#slash_add) - Event broadcast when commands are added
- [slash_remove](events.md#slash_remove) - Event broadcast when commands are removed

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_register":`).
