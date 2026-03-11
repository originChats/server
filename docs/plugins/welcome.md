# Welcome Plugin

Automatically sends a welcome message to users when they connect to the server.

Note: This plugin listens to the `user_connect` **plugin event**, which is sent on every connection. The plugin has its own `first_time_only` configuration to control whether users are welcomed only once.

## Features

- Sends a welcome message when users connect
- Configurable welcome message and channel
- Support for first-time-only welcome messages (track users who have already been welcomed)
- Persistent storage of welcomed users across server restarts

## Configuration

Create or edit `plugins/welcome_config.json`:

```json
{
  "enabled": true,
  "welcome_channel": "general",
  "welcome_message": "Welcome {username} to the server! 🎉",
  "first_time_only": true
}
```

### Configuration Options

- `enabled`: (boolean) Enable or disable the welcome plugin
  - Default: `true`
- `welcome_channel`: (string) Channel name where welcome messages are sent
  - Default: `"general"`
- `welcome_message`: (string) Welcome message template
  - You can use `{username}` as a placeholder that will be replaced with the joining user's username
  - Default: `"Welcome {username} to the server! 🎉"`
- `first_time_only`: (boolean) Only welcome a user the first time they connect
  - If `true`, tracks which users have been welcomed and doesn't send to them again
  - If `false`, sends a welcome message every time a user connects
  - Default: `true`

## How It Works

1. User connects to the server and authenticates
2. Server triggers `user_connect` **plugin event** (happens for every connection)
3. Welcome plugin receives the event
4. Plugin checks if it should welcome the user:
   - If `first_time_only` is true, checks if user has been welcomed before
   - If user was previously welcomed, skips sending another message
5. Plugin sends welcome message to the configured channel
6. Message is broadcast to all clients in the channel
7. Plugin saves the user as welcomed (if tracking first-time users)

## Relationship to user_join Event

The plugin operates independently from the `user_join` server broadcast:

- **`user_join` broadcast**: Sent by server when a new user first joins (once ever)
  - Clients receive this automatically
  - Used for showing new member notifications
  - Not used by this plugin

- **`user_connect` plugin event**: Sent by server for every successful authentication
  - Only plugins receive this event
  - Welcome plugin listens to this
  - Plugin applies its own `first_time_only` logic

This allows flexibility:
- Want to welcome every connection? Set `first_time_only: false`
- Want to welcome only first-time users? Set `first_time_only: true`
- Want to show different messages? The `user_join` event notifies all clients of new members, while the welcome plugin sends a channel message

## User Tracking

The plugin tracks which users have been welcomed in `plugins/welcomed_users.json`.

### Welcomed Users File

```json
[
  "USR:abc123def456",
  "USR:789xyz012345"
]
```

- Array of user IDs who have received a welcome message
- Persistent across server restarts
- Manually edit this file to reset a user (remove their ID from the list)

### Resetting Welcome Status

To reset a user's welcome status (so they get welcomed again):

**Option 1: Edit the file manually**
```bash
nano plugins/welcome/welcomed_users.json
# Remove the user ID from the array
```

**Option 2: Delete the file**
```bash
rm plugins/welcome/welcomed_users.json
# This causes all users to get welcomed again (like first-time users)
```

## Examples

### Basic Welcome

```json
{
  "enabled": true,
  "welcome_channel": "general",
  "welcome_message": "Welcome {username}!",
  "first_time_only": true
}
```

Result: New user "alice" receives "Welcome alice!" in #general

### Detailed Welcome

```json
{
  "enabled": true,
  "welcome_channel": "general",
  "welcome_message": "Welcome {username}! 🎉\n\nPlease read the rules in #rules and have fun!",
  "first_time_only": true
}
```

Result: Multi-line welcome message sent to #general

### Welcome Every Time

```json
{
  "enabled": true,
  "welcome_channel": "general",
  "welcome_message": "Welcome back, {username}!",
  "first_time_only": false
}
```

Result: Users get "Welcome back, {username}!" every time they connect

### Channel-Specific Welcome

```json
{
  "enabled": true,
  "welcome_channel": "welcome-room",
  "welcome_message": "Welcome {username}! Please introduce yourself.",
  "first_time_only": true
}
```

Result: Welcome message sent to #welcome-room instead of #general

## Installation

The welcome plugin is included in the `plugins/` directory. Make sure:

1. `welcome.py` exists in the `plugins/` directory
2. `welcome_config.json` exists in the `plugins/` directory (optional, will use defaults if missing)
3. The welcome channel exists in your server

## Troubleshooting

### Welcome Messages Not Appearing

1. Check if plugin is enabled:
   ```bash
   grep "enabled" plugins/welcome_config.json
   # Should show "enabled": true
   ```

2. Check server logs for errors:
   ```bash
   # Look for "Welcome plugin error" messages
   ```

3. Verify the welcome channel exists:
   ```bash
   # Check your channels.json
   # The welcome_channel should be a valid channel name
   ```

4. Check if user was already welcomed:
   ```bash
   cat plugins/welcome/welcomed_users.json
   # If the user ID is there, they won't get welcomed again (if first_time_only is true)
   ```

### Channel Not Found Error

If you see "Channel 'X' not found":
- The configured welcome channel doesn't exist
- Create the channel or update `welcome_channel` in the config

### Users Not Getting Welcomed

1. Check if `first_time_only` is true and they've been welcomed before
2. Check the `welcomed_users.json` file
3. Try setting `first_time_only` to false to test

## Permissions

The welcome plugin requires no special permissions to send messages. It sends messages as "System" user.

## Events

The plugin listens to the `user_connect` event from the server, which is triggered when a user successfully authenticates.

## Related

- [user_connect](plugin-development.md#event-user_connect) - Plugin event for user connections
- [user_join](../events/user_join_leave.md) - Server event broadcast for user joins
- [message_new](../commands/message_new.md) - Command for sending messages to channels

See implementation: `plugins/welcome.py`
