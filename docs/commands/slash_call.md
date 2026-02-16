# Command: slash_call

Execute a registered slash command.

## Request

```json
{
  "cmd": "slash_call",
  "channel": "<channel_name>",
  "command": "<command_name>",
  "args": {
    "<option_name>": <value>,
    // ... more options
  }
}
```

### Fields

- `channel`: (required) Channel name where the slash command is being invoked.
- `command`: (required) Name of the slash command to execute (without `/` prefix).
- `args`: (optional, default: `{}`) Object containing option values as key-value pairs.

## Response

### On Success

```json
{
  "cmd": "slash_call",
  "val": {
    "command": "<command_name>",
    "args": { ...args }
  },
  "invoker": "<user_id>",
  "channel": "<channel_name>",
  "global": true
}
```

The response is broadcast to all connected clients with `global: true`.

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "User roles not found"}`
- `{"cmd": "error", "val": "No server data provided"}`
- `{"cmd": "error", "val": "Channel parameter is required for slash commands"}`
- `{"cmd": "error", "val": "Command name must be a string"}`
- `{"cmd": "error", "val": "Unknown slash command: /<name>"}` - Command not registered
- `{"cmd": "error", "val": "Access denied: '<role>' role required"}` - Missing whitelist role
- `{"cmd": "error", "val": "Access denied: forbidden roles"}` - User has blacklisted role
- `{"cmd": "error", "val": "Command args must be an object"}` - `args` is not a JSON object
- `{"cmd": "error", "val": "Unknown argument: <name>"}` - Provided argument not in schema
- `{"cmd": "error", "val": "Missing required argument: <name>"}` - Required option not provided
- `{"cmd": "error", "val": "Invalid type for argument '<name>': expected <type>, got <type>"}` - Type validation failed
- `{"cmd": "error", "val": "Invalid value for argument '<name>': expected one of [...]"}` - Invalid enum choice

## Notes

- User must be authenticated.
- Slash commands must be registered via `slash_register` first.
- User must have the required roles (respecting `whitelistRoles` and `blacklistRoles`).
- `args` must be an object (JSON dict).
- All required args from the command schema must be provided.
- Type and enum choices are validated.
- On success, the execution is broadcast to all clients.
- Plugins can listen for `slash_call` events and execute custom logic.

## Command Validation

Before execution, the server validates:

1. **Command exists** - Command must be registered
2. **Role access** - User must have whitelist roles and NOT have blacklist roles
3. **Args format** - `args` must be JSON object
4. **Unknown args** - No extra args that aren't in the schema
5. **Required args** - All required args must be provided
6. **Type validation** - Values must match declared type
7. **Enum validation** - For enum types, value must be in choices array

## Usage Examples

### Command With No Args

```json
{
  "cmd": "slash_call",
  "channel": "general",
  "command": "ping"
}
```

### Command With Args

```json
{
  "cmd": "slash_call",
  "channel": "general",
  "command": "weather",
  "args": {
    "city": "London",
    "units": "metric"
  }
}
```

### Command With Complex Args

```json
{
  "cmd": "slash_call",
  "channel": "general",
  "command": "purge",
  "args": {
    "count": 10,
    "reason": "spam",
    "silent": true
  }
}
```

## Plugin Handling

Plugins can listen for `slash_call` commands via the plugin system:

```python
def on_slash_call(ws, data, server_data):
    command = data['val']['command']
    args = data['val']['args']
    invoker_id = data['invoker']
    channel = data['channel']
    
    # Execute custom logic
    result = handle_command(command, args)
    
    # Send custom response
    return {"cmd": "slash_response", "response": result}
```

## See Also

- [slash_register](slash_register.md) - Register slash commands with schema
- [slash_list](slash_list.md) - List all registered commands
- [slash_response](slash_response.md) - Response format for slash commands

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_call":`).

