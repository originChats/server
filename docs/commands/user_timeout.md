# Command: user_timeout

Set a rate limit timeout for a user (owner only).

## Request

```json
{
  "cmd": "user_timeout",
  "user": "<username_or_user_id>",
  "timeout": <timeout_in_seconds>
}
```

### Fields

- `user`: (required) Username or user ID of the user to timeout. Can be a username (which will be resolved to user ID) or a direct user ID.
- `timeout`: (required) Timeout duration in seconds. Must be a positive integer (can be 0 to remove timeout).

## Response

### On Success

```json
{
  "cmd": "user_timeout",
  "user": "<username>",
  "timeout": <timeout>
}
```

If the target user is currently connected, they will also receive:

```json
{
  "cmd": "rate_limit",
  "reason": "User timeout set",
  "length": <timeout * 1000>
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Timeout must be provided"}`
- `{"cmd": "error", "val": "Timeout must be a positive integer"}`

## Notes

- Requires `owner` role.
- The timeout is applied to the user's rate limiting system.
- A timeout of `0` removes any existing timeout (unlimits the user).
- The targeted user must be connected to receive the immediate notification.
- Setting a timeout causes the user to be immediately rate limited for the specified duration.
- The timeout affects all rate-limited actions (sending messages, etc.).
- Rate limiter must be enabled in server config for this command to work.

## Usage Examples

### Timeout User for 5 Minutes

```json
{
  "cmd": "user_timeout",
  "user": "alice",
  "timeout": 300
}
```

### Remove Timeout

```json
{
  "cmd": "user_timeout",
  "user": "alice",
  "timeout": 0
}
```

### Timeout by User ID

```json
{
  "cmd": "user_timeout",
  "user": "USR:1234567890abcdef",
  "timeout": 600
}
```

## See Also

- [user_ban](user_ban.md) - Ban a user permanently
- [user_unban](user_unban.md) - Unban a user
- [rate_limit_status](rate_limit_status.md) - Check rate limit status
- [rate_limit_reset](rate_limit_reset.md) - Reset rate limit (owner only)

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_timeout":`).
