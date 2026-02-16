# Command: rate_limit_reset

Reset a user's rate limiting (owner only).

## Request

```json
{
  "cmd": "rate_limit_reset",
  "user": "<username_or_user_id>"
}
```

### Fields

- `user`: (required) Username or user ID of the user whose rate limit should be reset.

## Response

### On Success

```json
{
  "cmd": "rate_limit_reset",
  "user": "<username>",
  "val": "Rate limit reset for user <username>"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "User parameter is required"}`
- `{"cmd": "error", "val": "Rate limiter not available or disabled"}`

## Notes

- Requires `owner` role.
- Can accept username (resolved to user ID) or direct user ID.
- Clears all rate limiting counters for the specified user.
- Resets any active cooldown or rate limit status.
- Rate limiter must be enabled in server config for this command to work.
- Does not remove manual timeouts set via `user_timeout` (use `user_timeout` with value 0 for that).

## Usage Examples

### Reset by Username

```json
{
  "cmd": "rate_limit_reset",
  "user": "alice"
}
```

### Reset by User ID

```json
{
  "cmd": "rate_limit_reset",
  "user": "USR:1234567890abcdef"
}
```

## See Also

- [rate_limit_status](rate_limit_status.md) - Check rate limit status
- [user_timeout](user_timeout.md) - Set or remove manual timeout
- [Config: Rate Limiting](../data/config.md) - Server rate limiting configuration

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "rate_limit_reset":`).

