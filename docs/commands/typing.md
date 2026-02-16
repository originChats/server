# Command: typing

Send a typing indicator to other users in the channel.

## Request

```json
{
  "cmd": "typing",
  "channel": "<channel_name>"
}
```

### Fields

- `channel`: (required) Name of the text channel where the user is typing.

## Response

### On Success

The server broadcasts to all authenticated users with view permission on the channel:

```json
{
  "cmd": "typing",
  "user": "<your_username>",
  "channel": "<channel_name>",
  "global": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Channel name not provided"}`

## Notes

- User must be authenticated.
- This command is subject to rate limiting to prevent spam.
- **Recommended:** Debounce client-side - only send every 2-3 seconds while actively typing.
- Clients should display a "user is typing..." indicator that auto-hides after 3 seconds of no updates.
- Only users with `view` permission on the channel receive the typing indicator.
- This indicates typing status but does not send any message content.

## Best Practices

1. **Debounce on client:** Don't send on every keystroke
2. **Hide after timeout:** Clear the typing indicator if no update for 3 seconds
3. **Stop indicator:** When user sends a message, clears typing input, or leaves channel
4. **Prevent spam:** Rate limiting is enforced on the server

## Example Usage

```javascript
let typingDebounce;
let isTyping = false;

function onKeypress() {
  if (!isTyping) {
    sendTypingIndicator();
    isTyping = true;
  }

  clearTimeout(typingDebounce);
  typingDebounce = setTimeout(() => {
    isTyping = false;
  }, 3000);
}

function sendTypingIndicator() {
  ws.send(JSON.stringify({
    cmd: "typing",
    channel: currentChannel
  }));
}
```

## See Also

- [message_new](message_new.md) - Send an actual message

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "typing":`).
