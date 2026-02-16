# Command: user_ban

Ban a user from the server (owner only).

## Request

```json
{
  "cmd": "user_ban",
  "user": "<username_or_user_id>"
}
```

### Fields

- `user`: (required) Username or user ID of the user to ban. Can be a username (which will be resolved to user ID) or a direct user ID.

## Response

### On Success

```json
{
  "cmd": "user_ban",
  "user": "<username>",
  "banned": true
}
```

### On Failure

If the user was already banned or doesn't exist:

```json
{
  "cmd": "user_ban",
  "user": "<username>",
  "banned": false
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`

## Notes

- Requires `owner` role.
- Banned users cannot authenticate with the server.
- Banned users that are currently connected remain connected until they disconnect.
- Attempting to connect while banned results in `{"cmd": "auth_error", "val": "Access denied: You are banned from this server"}`.
- Ban is persistent (stored in users.json) across server restarts.
- Does not forcefully disconnect currently connected banned users.

## See Also

- [user_unban](user_unban.md) - Unban a user
- [user_timeout](user_timeout.md) - Temporary timeout instead of ban
- [user_leave](user_leave.md) - Disconnect a user from server

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_ban":`).
