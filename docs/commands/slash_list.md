# Command: slash_list

List all registered slash commands from all connections.

## Request

```json
{
  "cmd": "slash_list"
}
```

No additional parameters required.

## Response

### On Success

```json
{
  "cmd": "slash_list",
  "commands": [
    {
      "name": "help",
      "description": "Get help information",
      "options": [
        {
          "name": "topic",
          "description": "Topic to get help for",
          "type": "str",
          "required": false,
          "choices": null
        }
      ],
      "whitelistRoles": null,
      "blacklistRoles": null,
      "ephemeral": false,
      "registeredBy": "alice"
    },
    {
      "name": "ping",
      "description": "Check server status",
      "options": [],
      "whitelistRoles": ["user"],
      "blacklistRoles": null,
      "ephemeral": true,
      "registeredBy": "bob"
    },
    {
      "name": "weather",
      "description": "Get weather for a city",
      "options": [
        {
          "name": "city",
          "description": "City name",
          "type": "str",
          "required": true,
          "choices": null
        }
      ],
      "whitelistRoles": null,
      "blacklistRoles": null,
      "ephemeral": false,
      "registeredBy": "alice"
    }
  ]
}
```

The `commands` field contains an array of command objects, each including:
- `name`: Command name (with `/` prefix not included)
- `description`: Description of what the command does
- `options`: Array of option objects
  - `name`: Option name
  - `description`: Option description
  - `type`: Data type - `"str"`, `"int"`, `"float"`, `"bool"`, or `"enum"`
  - `required`: Whether the option is required
  - `choices`: Array of valid choices (for `"enum"` type)
- `whitelistRoles`: Array of role names allowed to use this command (null if all roles)
- `blacklistRoles`: Array of role names NOT allowed to use this command
- `ephemeral`: Whether the command response is ephemeral
- `registeredBy`: Username of the user who registered the command

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "User roles not found"}`
- `{"cmd": "error", "val": "No server data provided"}`

## Notes

- User must be authenticated.
- Commands from all connections are returned, not just the requesting user's connections.
- Each command includes the `registeredBy` field showing the username of the user who registered it.
- Returns an empty array if no commands are registered: `{"cmd": "slash_list", "commands": []}`.
- This response **is not global** - it's sent only to the requesting client.
- The response format is a structured JSON array, not a formatted string, making it easier for clients to parse and display.

## Automatic Updates vs Manual Refresh

Clients have two ways to get command information:

### 1. Automatic Updates (Recommended)
Listen for `slash_add` and `slash_remove` events to maintain command state automatically:

```javascript
let commands = {};

// Initial fetch
fetchCommands();

function fetchCommands() {
  ws.send(JSON.stringify({cmd: 'slash_list'}));
}

// Handle automatic updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.cmd) {
    case 'slash_list':
      commands = {};
      data.commands.forEach(cmd => {
        commands[cmd.name] = cmd;
      });
      updateUI();
      break;

    case 'slash_add':
      data.commands.forEach(cmd => {
        commands[cmd.name] = cmd;
      });
      updateUI();
      break;

    case 'slash_remove':
      data.commands.forEach(cmdName => {
        delete commands[cmdName];
      });
      updateUI();
      break;
  }
};
```

### 2. Manual Refresh
Call `slash_list` periodically to get the full command list:

```javascript
setInterval(() => {
  ws.send(JSON.stringify({cmd: 'slash_list'}));
}, 60000); // Refresh every 60 seconds
```

## Per-Connection Commands

Commands are now registered per WebSocket connection:
- Each connection can have its own set of commands
- Commands are associated with the username of the user who registered them
- When a connection disconnects, all commands registered by that connection are removed
- The `registeredBy` field helps identify which user owns each command

## Command Data Structure

### Option Object

Each option in a command has the following structure:

```json
{
  "name": "city",
  "description": "City name",
  "type": "str",
  "required": true,
  "choices": null
}
```

For enum-type options, the `choices` array is required:

```json
{
  "name": "mood",
  "description": "Your mood",
  "type": "enum",
  "required": true,
  "choices": ["happy", "sad", "excited", "tired"]
}
```

### Roles

- `whitelistRoles`: If set, only users with these roles can use the command
- `blacklistRoles`: If set, users with these roles cannot use the command (takes precedence over whitelist)
- Both can be `null`, meaning all roles can use the command (or the blacklist/whitelist is not applicable)

## Example Usage

```javascript
// Fetch all commands
ws.send(JSON.stringify({cmd: 'slash_list'}));

// Handle response
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'slash_list') {
    console.log(`Found ${data.commands.length} commands:`);

    data.commands.forEach(cmd => {
      console.log(`/${cmd.name} - ${cmd.description} (registered by @${cmd.registeredBy})`);

      if (cmd.options.length > 0) {
        console.log('  Options:');
        cmd.options.forEach(opt => {
          const req = opt.required ? '[required]' : '[optional]';
          console.log(`    --${opt.name} (${opt.type}) ${req}: ${opt.description}`);
          if (opt.choices) {
            console.log(`      Choices: ${opt.choices.join(', ')}`);
          }
        });
      }

      if (cmd.whitelistRoles) {
        console.log(`  Requires roles: ${cmd.whitelistRoles.join(', ')}`);
      }

      if (cmd.blacklistRoles) {
        console.log(`  Forbidden for: ${cmd.blacklistRoles.join(', ')}`);
      }

      if (cmd.ephemeral) {
        console.log(`  Response is ephemeral (only visible to caller)`);
      }
    });
  }
};
```

## See Also

- [slash_register](slash_register.md) - Register new slash commands
- [slash_call](slash_call.md) - Execute a slash command
- [slash_response](slash_response.md) - Response format from slash commands
- [slash_add](events.md#slash_add) - Event for new commands
- [slash_remove](events.md#slash_remove) - Event for removed commands

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_list":`).
