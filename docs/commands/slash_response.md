# Command: slash_response

Send a response to a slash command as a message in the specified channel.

This command is typically used in plugin handlers to send responses that are saved as regular messages.

## Request

```json
{
  "cmd": "slash_response",
  "channel": "<channel_name>",
  "response": "<response_text>",
  "invoker": "<optional_user_id>"
}
```

### Fields

- `channel`: (required) Channel name where the response message should be posted.
- `response`: (required) The response text to send as a message.
- `invoker`: (optional) User ID who invoked the original slash command. If omitted, uses the current authenticated user's ID.

## Response

### On Success

```json
{
  "cmd": "slash_response",
  "message": {
    "user": "<username>",
    "content": "<response_text>",
    "timestamp": 1722510000.123,
    "type": "message",
    "pinned": false,
    "id": "b1c2d3e4-5678-90ab-cdef-1234567890ab"
  },
  "invoker": "<user_id>",
  "channel": "<channel_name>",
  "global": true
}
```

The response is:
- Saved as a regular message in the channel's message history
- Broadcast to all clients with view permission (`global: true`)
- User IDs are converted to usernames

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "User roles not found"}`
- `{"cmd": "error", "val": "Channel parameter is required for slash commands"}`
- `{"cmd": "error", "val": "Slash response must be a string"}` - `response` is not a string
- `{"cmd": "error", "val": "Slash response cannot be empty"}` - `response` is empty or whitespace

## Notes

- User must be authenticated.
- The response is saved as a message in the channel, viewable in message history.
- The message is attributed to the `invoker` (or current user if not provided).
- `response` text is trimmed of leading/trailing whitespace.
- Response is broadcast globally to all users with view permission.

## Use Cases

### Plugin Handler Example

```python
def handle_slash_command(plugin, ws, data, server_data):
    command = data['val']['command']
    args = data['val']['args']
    invoker_id = data['invoker']
    channel = data['channel']
    
    result = process_command(command, args)
    
    # Send as message in channel
    return {
        "cmd": "slash_response",
        "channel": channel,
        "response": result,
        "invoker": invoker_id
    }
```

### Direct Usage

```json
{
  "cmd": "slash_response",
  "channel": "general",
  "response": "Weather in London is sunny, 20°C",
  "invoker": "USR:1234567890abcdef"
}
```

## Message Properties

The saved message has these properties:
- `user`: The invoker's username
- `content`: The response text
- `timestamp`: Current Unix timestamp
- `type`: Always `"message"`
- `pinned`: Always `false`
- `id`: Auto-generated UUID

## See Also

- [slash_call](slash_call.md) - Execute a slash command
- [slash_register](slash_register.md) - Register slash commands
- [message_new](message_new.md) - Send a regular message
- [Data: Message Object](../data/messages.md) - Message structure

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "slash_response":`).

