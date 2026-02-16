# Command: slash_list

List all registered slash commands.

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
  "val": "Registered Slash Commands (2):\n\n/help\n  Get help information\n  Whitelist roles: None\n  Blacklist roles: None\n    • No options\n\n  Ephemeral: No\n\n/ping\n  Check server status\n  Whitelist roles: user\n  Blacklist roles: None\n    • No options\n\n  Ephemeral: Yes"
}
```

The `val` field contains a formatted string listing all registered commands with:
- Command name (with `/` prefix)
- Description
- Whitelist roles (if any)
- Blacklist roles (if any)
- List of options (if any)
- Whether the command is ephemeral

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "No server data provided"}`

## Notes

- User must be authenticated.
- Returns a formatted text string meant for display to users.
- If no slash commands are registered, returns "Registered Slash Commands (0):\n\n"
- The output is human-readable and designed for CLI or simple text display.

## Example Output Format

```
Registered Slash Commands (3):

/help
  Get help information
  Whitelist roles: None
  Blacklist roles: None
    • No options

  Ephemeral: No

/weather
  Get weather for a city
  Whitelist roles: None
  Blacklist roles: None
    • city (str) [required]: Name of the city

  Ephemeral: No

/ban
  Ban a user
  Whitelist roles: admin, moderator
  Blacklist roles: None
    • user (str) [required]: Username to ban
    • reason (str) [required]: Reason for ban

  Ephemeral: Yes
```

## See Also

- [slash_register](slash_register.md) - Register slash commands
- [slash_call](slash_call.md) - Execute a slash command

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_list":`).

