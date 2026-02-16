# Command: user_unban

Unban a user from the server (owner only).

## Request

```json
{
  "cmd": "user_unban",
  "user": "<username_or_user_id>"
}
```

### Fields

- `user`: (required) Username or user ID of the user to unban. Can be a username (which will be resolved to user ID) or a direct user ID.

## Response

### On Success

```json
{
  "cmd": "user_unban",
  "user": "<username>",
  "unbanned": true
}
```

### On Failure

If the user wasn't banned or doesn't exist:

```json
{
  "cmd": "user_unban",
  "user": "<username>",
  "unbanned": false
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`

## Notes

- Requires `owner` role.
- Unbanned users can authenticate with the server normally.
- Unban is persistent (stored in users.json) across server restarts.
- If the user was already not banned, `unbanned` will be false but no error occurs.

## See Also

- [user_ban](user_ban.md) - Ban a user
- [user_timeout](user_timeout.md) - Temporary timeout instead of ban

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_unban":`).
