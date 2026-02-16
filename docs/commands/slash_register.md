# Command: slash_register

Register new slash commands (owner only).

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

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Commands must be provided as a list"}`
- `{"cmd": "error", "val": "No server data provided"}`
- `{"cmd": "error", "val": "Invalid command schema: ..."}` - When validation fails

## Notes

- Requires `owner` role.
- Can register multiple commands in a single request.
- Commands are validated against the SlashCommand schema.
- If a command with the same name already exists, it will be overwritten.
- Options support type validation and required fields.
- `whitelistRoles` and `blacklistRoles` control who can use the command (role-based access).
- `ephemeral` commands send responses only to the caller.

## Slash Command Lifecycle

1. Register via `slash_register` command
2. User calls it via `slash_call` command
3. Server validates inputs based on schema
4. Server executes callback or plugin handler
5. Response is sent back

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

- [slash_list](slash_list.md) - List all registered slash commands
- [slash_call](slash_call.md) - Execute a slash command
- [slash_response](slash_response.md) - Response format from slash commands

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_register":`).

