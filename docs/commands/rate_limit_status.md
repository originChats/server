# Command: rate_limit_status

Check a user's rate limiting status.

## Request

```json
{
  "cmd": "rate_limit_status",
  "user": "<optional_username_or_user_id>"
}
```

### Fields

- `user`: (optional) Username or user ID to check.
  - If omitted, checks your own rate limit status
  - Only `owner` role can check other users' status
  - Can be a username (resolved to user ID) or a direct user ID

## Response

### On Success

```json
{
  "cmd": "rate_limit_status",
  "user": "<username>",
  "status": {
    "remaining": 25,
    "limit": 30,
    "reset_time": 1722510300,
    "is_rate_limited": false,
    "wait_time": 0
  }
}
```

### Status Object Fields

- `remaining`: Number of actions remaining before hitting the limit
- `limit`: Total maximum actions per minute
- `reset_time`: Unix timestamp when the counter resets
- `is_rate_limited`: `true` if currently rate limited, `false` otherwise
- `wait_time`: Time in milliseconds to wait if rate limited (0 if not limited)

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: can only check your own rate limit status"}` - When non-owner checks another user
- `{"cmd": "error", "val": "Rate limiter not available or disabled"}` - When rate limiting is disabled in config

## Notes

- User must be authenticated.
- By default, only shows your own status.
- `owner` role can check any user's status.
- Rate limiter must be enabled in server config for this command to work.
- Useful for debugging rate limit issues or for monitoring spam.

## Usage Examples

### Check Your Own Status

```json
{
  "cmd": "rate_limit_status"
}
```

### Check Another User's Status (Owner Only)

```json
{
  "cmd": "rate_limit_status",
  "user": "alice"
}
```

### Check by User ID (Owner Only)

```json
{
  "cmd": "rate_limit_status",
  "user": "USR:1234567890abcdef"
}
```

## See Also

- [rate_limit_reset](rate_limit_reset.md) - Reset a user's rate limit (owner only)
- [user_timeout](user_timeout.md) - Set a user timeout (owner only)
- [Config: Rate Limiting](../data/config.md) - Server rate limiting configuration

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "rate_limit_status":`).

