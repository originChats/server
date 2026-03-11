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
    "command": "command_name",
    "args": { ...args },
    "commander": "username"
  },
  "invoker": "user_id",
  "invokerUsername": "username",
  "channel": "channel_name"
}
```

The response includes:
- `invoker`: The user ID of the user who invoked the command
- `invokerUsername`: The username of the user who invoked the command
- `commander`: The username of the user who registered this command
- The command name, args, and channel

**Important**: This response is **not global** - it's sent only to the channel or specific clients as needed. Plugins should listen for this event to execute custom logic.

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
- Commands are registered per-connection, but can be called by any authenticated user who meets the role requirements.
- User must have the required roles (respecting `whitelistRoles` and `blacklistRoles`) defined in the command schema.
- `args` must be an object (JSON dict).
- All required args from the command schema must be provided.
- Type and enum choices are validated.
- **The response is not broadcast globally** - it's sent only to the invoking client.
- Plugins can listen for `slash_call` events and execute custom logic.

## Command Validation

Before execution, the server validates:

1. **Command exists** - Command must be registered by any connection
2. **Role access** - User must have whitelist roles and NOT have blacklist roles (as defined by the command)
3. **Args format** - `args` must be JSON object
4. **Unknown args** - No extra args that aren't in the schema
5. **Required args** - All required args must be provided
6. **Type validation** - Values must match declared type
7. **Enum validation** - For enum types, value must be in choices array

## Per-Connection Command Behavior

- Commands are registered per WebSocket connection, but can be called by any authenticated user who has the required permissions.
- The server searches across all connections' registered commands when looking up a command name.
- When the connection that registered a command disconnects, that command becomes unavailable to all users.
- Command availability depends on the registering connection being connected to the server.
- The `commander` field in the response indicates which user registered the command.

## Non-Global Behavior

Unlike previous versions, slash_call responses are **not global**:
- Only the invoking client receives the response
- Plugins that want to broadcast responses should use `slash_response` with the appropriate settings
- This allows for more fine-grained control over command visibility

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

### Basic Plugin Handler

```python
def on_slash_call(ws, data, server_data):
    """Handle slash command invocations"""
    command = data['val']['command']
    args = data['val']['args']
    invoker_id = data['invoker']
    invoker_username = data.get('invokerUsername')
    channel = data['channel']
    commander = data['val'].get('commander')
    
    # Execute custom logic based on command
    if command == "weather":
        result = get_weather(args.get("city"))
    elif command == "ping":
        result = "Pong!"
    else:
        result = "Unknown command"
    
    # Send response - this creates a message in the channel
    # with interaction information
    return {
        "cmd": "slash_response",
        "channel": channel,
        "response": result,
        "invoker": invoker_id,
        "command": command
    }
```

### Advanced Plugin Handler

```python
def on_slash_call(ws, data, server_data):
    """Advanced slash command handler with error handling"""
    try:
        command = data['val']['command']
        args = data['val']['args']
        invoker_id = data['invoker']
        invoker_username = data.get('invokerUsername')
        channel = data['channel']
        commander = data['val'].get('commander')
        
        # Log command usage
        Logger.info(f"Command /{command} invoked by {invoker_username} in #{channel}")
        Logger.info(f"Command registered by {commander}")
        
        # Execute command
        result = handle_command(command, args)
        
        # Send response
        return {
            "cmd": "slash_response",
            "channel": channel,
            "response": str(result),
            "invoker": invoker_id,
            "command": command
        }
        
    except Exception as e:
        Logger.error(f"Error handling command: {e}")
        # Send error message
        return {
            "cmd": "slash_response",
            "channel": channel,
            "response": f"Error: {str(e)}",
            "invoker": invoker_id,
            "command": command
        }
```

## Response Flow

```
User invokes /command
        ↓
[slash_call request]
        ↓
[Validate command exists]
        ↓
[Validate user permissions]
        ↓
[Validate arguments]
        ↓
[Broadcast slash_call event to plugins]
        ↓
[Plugin handles command]
        ↓
[Plugin returns slash_response]
        ↓
[Create message with interaction]
        ↓
[Send message to channel]
```

## Interaction Information

When a slash_response is sent, it includes an `interaction` property in the message:

```json
{
  "id": "message-uuid",
  "user": "user_id",
  "content": "Response content here",
  "timestamp": 1234567890.123,
  "type": "message",
  "pinned": false,
  "interaction": {
    "command": "weather",
    "username": "invoker_username"
  }
}
```

This allows clients to:
- Show that the message was generated by a slash command
- Display which command was invoked
- Show who invoked the command
- Render special UI/UX for command responses

## See Also

- [slash_register](slash_register.md) - Register slash commands (per-connection)
- [slash_list](slash_list.md) - List all registered commands
- [slash_response](slash_response.md) - Response format for slash commands

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_call":`).
