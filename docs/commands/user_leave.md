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
  "user": "<your_username>",
  "val": "User left server",
  "global": true
}
```

The client that sent the command is then disconnected.

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Server data not available"}`

## Notes

- User must be authenticated.
- Any authenticated user can request to leave the server.
- **This action is irreversible** - the user's account is deleted from the database.
- All user data is removed (username, roles, etc.).
- The user will need to re-authenticate as a new user if they return.
- Only the requesting user's account is deleted, not other users.
- The user is removed from their voice channel (if in one) before deletion.
- User's messages remain in channel histories (not deleted).

## Use Cases

- User wants to permanently delete their account
- User wants to "restart" their account
- Cleanup of test accounts

## Alternatives

For temporary actions instead of leaving:
- Simply close the connection (account remains)
- Use [user_ban](user_ban.md) if you want to prevent reconnection (admin action)

## See Also

- [user_disconnect](../protocol.md#user-disconnect) - When a user is forcibly disconnected
- [user_ban](user_ban.md) - Ban a user (admin action)
- [user_timeout](user_timeout.md) - Temporary timeout

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_leave":`).
