# Common Errors

The server may respond with error objects for various reasons. All errors use the following format:

```json
{
  "cmd": "error",
  "val": "<error message>",
  "src": "<command_that_caused_error>"
}
```

Below is a comprehensive list of all error messages organized by category. Refer to the linked source files for exact logic.

---

## Error List

### Authentication & General

*Errors from: [handlers/auth.py](../handlers/auth.py), [server.py](../server.py), [handlers/helpers/validation.py](../handlers/helpers/validation.py), [handlers/message.py](../handlers/message.py)*

- **Access denied: You are banned from this server**
  - The user is banned and cannot authenticate.
- **Authentication failed**
  - Cracked authentication failed.
- **Authentication required**
  - The user is not logged in or trying to access protected resources.
- **Invalid authentication**
  - Rotur authentication validation failed.
- **Invalid message format: expected a dictionary, got ...**
  - The client sent a message that is not a JSON object.
- **Registration failed**
  - Cracked registration failed.
- **Registration is disabled**
  - Cracked registration attempt when disabled.
- **Rotur authentication is disabled. Use login or register commands.**
  - Auth mode is cracked-only.
- **Server data not available**
  - A command requires server state that is not available.
- **Unknown command: ...**
  - The `cmd` field is missing or not recognized by the server.
- **User not found**
  - The user does not exist in the database after authentication.
- **Username and password required**
  - Cracked auth attempt without username or password.

---

### Messages

*Errors from: [handlers/messages/message.py](../handlers/messages/message.py), [handlers/messages/message_edit.py](../handlers/messages/message_edit.py), [handlers/messages/message_delete.py](../handlers/messages/message_delete.py), [handlers/messages/message_pin.py](../handlers/messages/message_pin.py), [handlers/messages/messages.py](../handlers/messages/messages.py)*

#### Creating & Sending Messages

- **Attachments are disabled**
  - The attachments feature is turned off.
- **Attachments must be an array**
  - Invalid attachments format provided.
- **Attachment ... not found or expired**
  - The attachment doesn't exist or has expired.
- **Attachment ID is required**
  - Missing attachment ID in request.
- **Cannot send messages in this channel type**
  - Wrong channel type for sending messages.
- **Channel not found**
  - The specified channel does not exist.
- **Each attachment must be an object**
  - Invalid attachment item format.
- **Failed to save message**
  - Message could not be saved to database.
- **Message content or attachments cannot be empty**
  - The message has no content or attachments.
- **Message too long. Maximum length is ... characters**
  - The message exceeds the configured length limit.
- **Missing fields: ...**
  - Required fields are missing in a `message_new` request.
- **Rate limited**
  - The user is sending messages too quickly.
- **The message you're trying to reply to was not found**
  - The `reply_to` message ID does not exist in the channel.
- **Thread not found**
  - The specified thread does not exist.
- **This thread is locked**
  - Cannot send messages in a locked thread.
- **You can only attach your own uploads**
  - User attempted to attach another user's upload.
- **You do not have permission to send messages in this channel**
  - User lacks send permission in channel.
- **You do not have permission to send messages in this thread**
  - User lacks send permission in thread.

#### Editing Messages

- **Channel or thread not found**
  - Message edit context not found.
- **Failed to edit message**
  - Message could not be edited.
- **Invalid message edit format**
  - Required fields missing in `message_edit` request.
- **Message not found or cannot be edited**
  - The message does not exist or cannot be edited.
- **You do not have permission to edit your own message in this channel/thread**
  - User's roles do not allow editing their own messages.
- **You do not have permission to edit this message**
  - User tried to edit someone else's message without permission.

#### Deleting Messages

- **Failed to delete message**
  - Message could not be deleted.
- **Invalid message delete format**
  - Required fields missing in `message_delete` request.
- **Message not found or cannot be deleted**
  - The message does not exist or cannot be deleted.
- **You do not have permission to delete your own message in this channel/thread**
  - User's roles do not allow deleting their own messages.
- **You do not have permission to delete this message**
  - User is not the sender and lacks delete permission.

#### Pinning Messages

- **Channel name not provided**
  - Missing channel for pin command.
- **Message ID is required**
  - Missing message ID for pin/unpin.
- **You do not have permission to pin messages in this channel**
  - User's roles do not allow pinning messages.

#### Fetching Messages

- **around (message ID) is required**
  - Missing around parameter for messages_around.
- **Channel name and message ID are required**
  - Missing parameters for message replies.
- **Channel name and query are required**
  - Missing parameters for message search.
- **Channel/thread and message ID are required**
  - Missing parameters for message_get.
- **Message not found**
  - The requested message does not exist.
- **Channel or thread not found**
  - The specified context does not exist.
- **Channel or thread_id is required**
  - Neither channel nor thread_id provided.

#### Typing Indicators

- **Access denied to this channel**
  - User does not have permission to view the channel for typing.
- **User not found**
  - User not in database for typing indicator.

---

### Channels

*Errors from: [handlers/messages/channel.py](../handlers/messages/channel.py), [handlers/helpers/validation.py](../handlers/helpers/validation.py)*

- **Access denied to this channel**
  - The user does not have permission to view the channel.
- **Channel already exists**
  - Attempting to create a channel with existing name.
- **Channel name is required**
  - Missing channel name in request.
- **Channel not found**
  - The specified channel does not exist.
- **Channel with new name already exists**
  - Rename would cause name conflict.
- **current_name is required**
  - Missing current name for channel update.
- **Failed to create channel**
  - Channel creation failed.
- **Failed to update channel**
  - Channel update failed.
- **Invalid channel type**
  - Invalid channel type in update.
- **Invalid channel type, must be text, voice, or separator**
  - Wrong channel type value.
- **Channel type is required (text, voice, or separator)**
  - Missing channel type in creation.
- **Position must be a non-negative integer**
  - Invalid position value.
- **Position is required**
  - Missing position for channel move.
- **This is not a text channel**
  - A text-only command was used on a non-text channel.
- **This is not a voice channel**
  - A voice command was used on a non-voice channel.
- **updates object is required**
  - Missing updates in channel update.

---

### Users & Roles

*Errors from: [handlers/messages/user.py](../handlers/messages/user.py), [handlers/messages/role.py](../handlers/messages/role.py), [handlers/messages/self_role.py](../handlers/messages/self_role.py), [handlers/helpers/validation.py](../handlers/helpers/validation.py)*

#### User Profile

- **Cannot update field: ...**
  - Forbidden field in user update.
- **Failed to update profile picture**
  - Profile picture update failed.
- **Invalid URL format**
  - Invalid profile picture URL.
- **Nickname must be a string or null**
  - Invalid nickname format.
- **Profile pictures are managed by Rotur for this account**
  - PFP set on non-cracked account.
- **Target user not found**
  - Target user missing after database operation.
- **URL required**
  - Missing profile picture URL.
- **URL too long (max 500 characters)**
  - Profile picture URL exceeds limit.
- **Updates must be an object**
  - Invalid updates format.
- **User ID is required**
  - Missing user ID in request.
- **User not found**
  - The user does not exist in the database.
- **Username must be a non-empty string**
  - Invalid username format.
- **Username required**
  - Missing username for profile lookup.

#### Role Management

- **Access denied: '...' role required**
  - Missing required role.
- **Cannot delete system roles**
  - Attempting to delete owner/admin/user roles.
- **Cannot rename role: it is used in channel '...' permissions**
  - Role is in use by channel permissions.
- **Failed to reorder roles**
  - Role reorder operation failed.
- **Role already exists**
  - Duplicate role creation.
- **Role '...' cannot be made self-assignable**
  - Role not eligible for self-assignment.
- **Role data is required**
  - Missing role_set data.
- **Role id or name is required**
  - Missing role identifier.
- **Role is used in channel '...' permissions**
  - Cannot delete role in use.
- **Role not found**
  - The specified role does not exist.
- **Role not found after update**
  - Role missing after database operation.
- **Role '...' does not exist**
  - Specified role doesn't exist.
- **Roles array is required**
  - Invalid roles format for reorder.
- **Roles list is required**
  - Missing roles list in request.
- **User roles not found**
  - Server could not find roles for the user.

#### Self-Assignable Roles

- **Failed to assign role**
  - Role assignment failed.
- **Failed to remove role**
  - Role removal failed.
- **Role name is required**
  - Missing role name.
- **Role not found**
  - The specified role does not exist.
- **This role is not self-assignable**
  - Role not marked as self-assignable.
- **You already have this role**
  - User already has the role.
- **You don't have this role**
  - User doesn't have the role to remove.

---

### Threads

*Errors from: [handlers/message.py](../handlers/message.py)*

- **Channel and thread name are required**
  - Missing thread creation parameters.
- **Channel not found**
  - Parent channel for thread not found.
- **Failed to delete message**
  - Thread message deletion failed.
- **Message ID is required**
  - Missing message ID for embeds.
- **Thread ID is required**
  - Missing thread identifier.
- **Thread name cannot be empty**
  - Empty thread name provided.
- **Thread not found**
  - The specified thread does not exist.
- **Threads can only be created in forum channels**
  - Wrong channel type for thread creation.
- **This thread is locked**
  - Thread is locked.
- **This thread is archived**
  - Thread is archived.
- **You do not have permission to create threads in this channel**
  - Missing create_thread permission.
- **You do not have permission to delete this thread**
  - Missing delete permission.
- **You do not have permission to join this thread**
  - Missing join permission.
- **You do not have permission to update this thread**
  - Missing update permission.
- **You do not have permission to view this thread**
  - Missing view permission.

---

### Voice Channels

*Errors from: [handlers/helpers/validation.py](../handlers/helpers/validation.py), [handlers/message.py](../handlers/message.py)*

- **Authentication required**
  - Not authenticated for voice operations.
- **Channel name is required**
  - Missing channel for voice command.
- **Peer ID is required**
  - Missing peer_id for voice channel join.
- **Server data not available**
  - Missing server data for voice operations.
- **User not found**
  - User not in database for voice.
- **Voice channel no longer exists**
  - The voice channel has been deleted.
- **You are not in a voice channel**
  - User not in any voice channel.
- **You are not in this voice channel**
  - User's session has stale voice channel data.
- **You do not have permission to access this voice channel**
  - No voice channel access.

---

### Reactions

*Errors from: [handlers/messages/reaction.py](../handlers/messages/reaction.py)*

- **Failed to add reaction**
  - Reaction could not be added.
- **Failed to remove reaction**
  - Reaction could not be removed.
- **Message ID and emoji are required**
  - Missing reaction parameters.
- **Message not found**
  - The message does not exist.
- **User ID is required**
  - Missing user identifier.
- **You do not have permission to add reactions to this message**
  - No reaction permission.
- **You do not have permission to remove reactions from this message**
  - No remove reaction permission.

---

### Polls

*Errors from: [handlers/messages/poll.py](../handlers/messages/poll.py)*

- **At least 2 options are required**
  - Not enough poll options.
- **Cannot have more than 10 options**
  - Too many poll options.
- **Channel or thread_id is required**
  - Missing poll location.
- **Channel not found**
  - Channel for poll not found.
- **Failed to end poll**
  - Poll end operation failed.
- **Option ... must have 'text'**
  - Missing option text.
- **poll_id or message_id is required**
  - Missing poll identifier.
- **Poll has already ended**
  - Attempting to vote on ended poll.
- **Poll not found**
  - The specified poll does not exist.
- **Poll results not found**
  - Results data missing.
- **Question is required**
  - Missing poll question.
- **Thread not found**
  - Thread for poll not found.
- **You do not have permission to view this poll**
  - No poll view permission.
- **You do not have permission to send messages in this channel/thread**
  - No send permission for poll creation.
- **option_id or option_ids is required**
  - Missing vote option.
- **User ID is required**
  - Missing user identifier.

---

### Webhooks

*Errors from: [handlers/messages/webhook.py](../handlers/messages/webhook.py), [server.py](../server.py)*

- **Channel is required**
  - Missing webhook channel.
- **Channel not found**
  - Webhook channel doesn't exist.
- **Content-Type must be application/json**
  - Wrong webhook content type.
- **Failed to create webhook**
  - Webhook creation failed.
- **Failed to delete webhook**
  - Webhook deletion failed.
- **Failed to regenerate webhook token**
  - Token regeneration failed.
- **Failed to save attachment**
  - Webhook attachment save failed.
- **Failed to update webhook**
  - Webhook update failed.
- **Invalid JSON body**
  - Malformed webhook JSON.
- **Invalid webhook token**
  - Webhook token is invalid.
- **No content provided**
  - Webhook has no content.
- **No updates provided**
  - No webhook update fields.
- **Request body too large (max 10MB)**
  - Webhook body too large.
- **Webhook ID is required**
  - Missing webhook identifier.
- **Webhook name must be a non-empty string**
  - Invalid webhook name.
- **Webhook name is required**
  - Missing webhook name.
- **Webhook not found**
  - The specified webhook does not exist.
- **Webhook token required**
  - Missing webhook token.
- **Webhooks can only be created for text channels**
  - Wrong channel type for webhook.

---

### Emojis

*Errors from: [handlers/messages/emoji.py](../handlers/messages/emoji.py), [server.py](../server.py)*

- **At least one field to update is required (name or image)**
  - No emoji update fields.
- **Emoji not found**
  - The specified emoji does not exist.
- **Emoji file not found**
  - Emoji file missing on disk.
- **Error adding emoji**
  - Emoji add operation failed.
- **Invalid emoji_* command scheme: ...**
  - Schema validation error.
- **Server asset not found**
  - Server asset file missing.
- **Emoji not found**
  - Emoji file not found on server.

---

### Attachments

*Errors from: [handlers/messages/attachment.py](../handlers/messages/attachment.py), [server.py](../server.py)*

- **Attachment file not found**
  - Attachment file missing on disk.
- **Attachment ID required**
  - Missing attachment ID.
- **Attachment not found**
  - Attachment missing in database.
- **Attachment not found or expired**
  - Attachment doesn't exist or expired.
- **Attachments are disabled**
  - Attachments feature disabled.
- **Content-Type must be application/json**
  - Wrong upload content type.
- **Failed to delete attachment**
  - Attachment deletion failed.
- **Failed to read request body**
  - Error reading upload body.
- **Failed to save attachment**
  - Attachment save failed.
- **Invalid JSON body**
  - Malformed upload JSON.
- **Missing required fields: file, name, mime_type, channel**
  - Missing upload fields.
- **Request body too large (max ... bytes)**
  - Upload exceeds size limit.
- **You can only delete your own attachments**
  - Not attachment owner.
- **You don't have permission to send in this channel**
  - No send permission for upload.

---

### Push Notifications

*Errors from: [handlers/push.py](../handlers/push.py)*

- **Failed to remove subscription**
  - Push subscription removal failed.
- **Failed to save subscription**
  - Push subscription save failed.
- **Missing endpoint**
  - No endpoint provided for unsubscription.
- **Missing subscription object**
  - No subscription data provided.
- **Not authenticated**
  - User not logged in for push operations.
- **subscription must include endpoint, keys.p256dh and keys.auth**
  - Incomplete subscription data.
- **VAPID keys not configured on this server**
  - VAPID keys not available.

---

### Slash Commands

*Errors from: [handlers/messages/slash.py](../handlers/messages/slash.py), [slash_handlers/ban.py](../slash_handlers/ban.py), [slash_handlers/mute.py](../slash_handlers/mute.py), [slash_handlers/unban.py](../slash_handlers/unban.py), [slash_handlers/unmute.py](../slash_handlers/unmute.py), [slash_handlers/nick.py](../slash_handlers/nick.py)*

#### Command Registration & Execution

- **Access denied: forbidden roles**
  - User has blacklisted role.
- **Access denied: '...' role required**
  - Missing whitelisted role.
- **Channel parameter is required for slash commands**
  - Missing channel for slash command.
- **Command args must be an object**
  - Invalid args format.
- **Command handler for /... is not currently connected**
  - Handler offline.
- **Command name must be a string**
  - Invalid command name.
- **Commands must be provided as a list**
  - Invalid commands format.
- **Command parameter is required for slash responses**
  - Missing command param.
- **Error executing command: ...**
  - Command execution exception.
- **Invalid command schema: ...**
  - Schema validation failed.
- **Missing required argument: ...**
  - Missing required argument.
- **No server data provided**
  - Missing server data.
- **Slash response must be a string**
  - Invalid response type.
- **Slash response must have content or embeds**
  - Empty response.
- **Unknown argument: ...**
  - Invalid argument name.
- **Unknown slash command: /...**
  - Command not found.
- **You already have slash commands registered from another session**
  - Duplicate session.

#### Ban Command

- **Cannot ban the server owner**
  - Attempting to ban owner.
- **User '...' is already banned**
  - User already banned.
- **User '...' not found**
  - User to ban not found.
- **Username is required**
  - Missing ban username.

#### Mute Command

- **Cannot mute the server owner**
  - Attempting to mute owner.
- **Duration must be a positive number**
  - Invalid duration value.
- **Duration must be a valid number**
  - Non-numeric duration.
- **Duration is required**
  - Missing mute duration.
- **Rate limiter not available**
  - No rate limiter for mute.
- **User '...' not found**
  - User to mute not found.
- **Username is required**
  - Missing mute username.

#### Unban Command

- **User '...' is not banned**
  - User not banned.
- **User '...' not found**
  - User to unban not found.
- **Username is required**
  - Missing unban username.

#### Unmute Command

- **Rate limiter not available**
  - No rate limiter for unmute.
- **User '...' not found**
  - User to unmute not found.
- **Username is required**
  - Missing unmute username.

#### Nick Command

- **Nickname too long (max ... characters)**
  - Nickname exceeds limit.
- **Not authenticated**
  - Not logged in.
- **User not found**
  - User not in database.

---

### Server Management

*Errors from: [handlers/messages/server.py](../handlers/messages/server.py)*

- **Banner must be a string or null**
  - Invalid banner format.
- **Icon must be a string or null**
  - Invalid icon format.
- **Name must be a string or null**
  - Invalid server name format.
- **No updates provided**
  - No server update fields.

---

### Plugins

*Errors from: [handlers/message.py](../handlers/message.py)*

- **Failed to reload plugin '...'**
  - Plugin reload failed.
- **Plugin manager not available**
  - Plugin manager not loaded.

---

### Rate Limiting

*Errors from: [handlers/message.py](../handlers/message.py), [handlers/messages/rate_limit.py](../handlers/messages/rate_limit.py)*

- **Access denied: can only check your own rate limit status**
  - Only user or owner can check rate limit.
- **Rate limiter not available or disabled**
  - Rate limiter not enabled.
- **User parameter is required**
  - Missing user for rate limit check.

---

### Moderation

*Errors from: [handlers/message.py](../handlers/message.py)*

- **Timeout must be a positive integer**
  - Invalid timeout value.
- **User parameter is required**
  - Missing target for moderation actions.

---

### Embeds

*Errors from: [handlers/message.py](../handlers/message.py)*

- **Channel or thread not found**
  - Context for embeds not found.
- **Channel or thread_id is required**
  - Missing embeds context.
- **Message ID is required**
  - Missing message ID for embeds.
- **Message not found**
  - Message for embeds not found.

---

### Permissions

*Errors from: [handlers/helpers/validation.py](../handlers/helpers/validation.py)*

- **Access denied: '...' permission required**
  - Missing required permission.
- **Cannot use this command in this channel type**
  - Wrong channel type for command.

---

### GitHub Webhooks

*Errors from: [handlers/github_webhook.py](../handlers/github_webhook.py), [server.py](../server.py)*

- **Channel not found**
  - Webhook channel missing.
- **Failed to read request body**
  - Error reading webhook body.
- **GitHub webhook error**
  - GitHub webhook processing error.
- **Invalid JSON body**
  - Malformed webhook JSON.
- **Request body too large (max 10MB)**
  - Webhook body too large.
- **User ID not found in authentication response**
  - API response missing user ID.
- **validator_key and validator are required for authentication**
  - Missing auth credentials.

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

## HTTP Error Responses

The server also returns HTTP errors for API endpoints:

### 400 Bad Request
- Attachment ID required
- Content-Type must be application/json
- Failed to read request body
- Invalid JSON body
- Invalid credentials
- Missing required fields
- Request body too large

### 401 Unauthorized
- Authentication required
- Failed to validate credentials
- Invalid webhook token
- validator_key and validator are required

### 403 Forbidden
- You don't have permission to send in this channel

### 404 Not Found
- Attachment not found or expired
- Attachment file not found
- Channel not found
- Emoji not found
- Server asset not found
- User not found
- Webhook not found

### 413 Payload Too Large
- Request body too large (max ... bytes)

### 415 Unsupported Media Type
- Content-Type must be application/json

### 500 Internal Server Error
- Failed to save attachment

### 502 Bad Gateway
- Failed to validate credentials

### 503 Service Unavailable
- Attachments are disabled

---

For more details, see the linked source files.
