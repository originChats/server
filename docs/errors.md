# Common Errors

The server may respond with error objects for various reasons. All errors use the following format:

```json
{
  "cmd": "error",
  "val": "<error message>",
  "src": "<command_that_caused_error>"
}
```

Below is a list of common error messages and what they mean. Refer to the [source code](../handlers/message.py) for exact logic.

---

## Error List

### Authentication & General

- **User not authenticated**
  - The user is not logged in or the WebSocket session is missing authentication.
- **Invalid message format: expected a dictionary, got ...**
  - The client sent a message that is not a JSON object.
- **Unknown command: ...**
  - The `cmd` field is missing or not recognized by the server.
- **Server data not available**
  - A command requires server state that is not available.

### Messages

- **Invalid chat message format**
  - Required fields are missing in a `message_new` request.
- **Message content cannot be empty**
  - The message text is empty or only whitespace.
- **Message too long. Maximum length is ... characters**
  - The message exceeds the configured length limit.
- **Rate limited**
  - The user is sending messages too quickly. (See also the `rate_limit` response.)
- **The message you're trying to reply to was not found**
  - The `reply_to` message ID does not exist in the channel.
- **Failed to edit message**
  - The message could not be edited (may not exist or user lacks permission).
- **Invalid message edit format**
  - Required fields are missing in a `message_edit` request.
- **Message not found or cannot be edited**
  - The message does not exist or cannot be edited.
- **You do not have permission to edit your own message in this channel**
  - The user's roles do not allow editing their own messages.
- **You do not have permission to edit this message**
  - The user tried to edit someone else's message and does not have permission.
- **Message not found or cannot be deleted**
  - The message does not exist or cannot be deleted.
- **You do not have permission to delete your own message in this channel**
  - The user's roles do not allow deleting their own messages.
- **You do not have permission to delete this message**
  - The user is not the sender and lacks delete permission.
- **Invalid message delete format**
  - Required fields are missing in a `message_delete` request.
- **You do not have permission to pin messages in this channel**
  - The user's roles do not allow pinning messages.

### Channels

- **Invalid channel name**
  - The channel name is missing or invalid.
- **Access denied to this channel**
  - The user does not have permission to view the channel.
- **This is not a text channel**
  - A text-only command was used on a non-text channel.
- **This is not a voice channel**
  - A voice command was used on a non-voice channel.

### Users & Roles

- **User not found**
  - The user does not exist in the database.
- **User roles not found**
  - The server could not find any roles for the user.
- **Access denied: owner role required**
  - The command requires the `owner` role.

### Plugions & System

- **Plugin manager not available**
  - The plugin manager is not loaded or available in the server state.
- **Failed to reload plugin '...'**
  - The named plugin could not be reloaded.

### Rate Limiting

- **Rate limiter not available or disabled**
  - The rate limiter is not enabled in the server state.
- **Access denied: can only check your own rate limit status**
  - Only the user or an owner can check rate limit status for a user.
- **User parameter is required**
  - The `user` field is missing in a request that requires it (e.g., timeout, ban).

### Voice Channels

- **You are not in a voice channel**
  - The command requires being in a voice channel, but the user is not.
- **Voice channel no longer exists**
  - The voice channel has been deleted or no longer exists.
- **You are not in this voice channel**
  - The user's session has stale voice channel data.
- **Channel name is required**
  - Voice commands require a channel name.
- **Peer ID is required**
  - The `peer_id` field is required for joining a voice channel.
- **You do not have permission to view this voice channel**
  - The user lacks view permission on the voice channel.

### Commands

- **Channel parameter is required for slash commands**
  - A slash command was called without specifying a channel.
- **Slash command parameter is required**
  - A slash command was invoked without a command name.

---

## Special Responses

### Rate Limit

Not technically an error, but similar format:

```json
{
  "cmd": "rate_limit",
  "length": <milliseconds>
}
```

The client should wait the specified time before retrying.

---

For more details, see [`handlers/message.py`](../handlers/message.py).

