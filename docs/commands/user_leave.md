# Command: user_leave

Request to leave the server and delete the user's account.

## Request

```json
{
  "cmd": "user_leave"
}
```

No additional parameters required.

## Response

### On Success

The server broadcasts to all connected clients:

```json
{
  "cmd": "user_leave",
  "username": "your_username",
  "val": "User left server"
}
```

The client that sent the command is then disconnected.

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Server data not available"}`

## Notes

- User must be authenticated.
- Any authenticated user can request to leave the server.
- **This action is irreversible** - the user's account is deleted from the database (unless banned).
- **Ban exception**: If the user is banned, their account is NOT deleted from the database. This preserves ban records and prevents circumvention.
- All user data is removed (username, roles, etc.) for non-banned users.
- The user will need to re-authenticate as a new user if they return (unless they were banned).
- Only the requesting user's account is deleted, not other users.
- The user is removed from their voice channel (if in one) before deletion.
- User's messages remain in channel histories (not deleted).

## Banned Users

When a banned user attempts to leave:

**Server Behavior:**
- User account is **preserved** in `users.json`
- Ban record remains intact
- Warning is logged: `"User {username} (ID: {user_id}) is banned, keeping in database"`

**Client Experience:**
- The `user_leave` event is still broadcast to all clients
- The user is removed from any voice channels
- The WebSocket connection is closed
- User appears to have left, but their account data is retained

**Purpose:**
- Maintains ban enforcement and audit trail
- Prevents banned users from deleting and recreating accounts
- Allows admins to track banned users even after they disconnect

## Use Cases

- User wants to permanently delete their account
- User wants to "restart" their account
- Cleanup of test accounts

## Alternatives

For temporary actions instead of leaving:
- Simply close the connection (account remains)
- Use [user_ban](user_ban.md) if you want to prevent reconnection (admin action)

## Plugin Event

The `user_leave` plugin event is triggered with:

```python
{
    "username": "your_username",
    "user_id": "your_user_id"
}
```

Plugins can listen for this event to handle custom cleanup or logging.

## See Also

- [user_connect](../events/user_join_leave.md#user_connect) - User connects (online status)
- [user_disconnect](../events/user_join_leave.md#user_disconnect) - User disconnects (online status)
- [user_join](../events/user_join_leave.md#user_join) - New user joins
- [user_ban](user_ban.md) - Ban a user

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_leave":`).
