# Command: users_banned_list

List all banned users on the server (owner only).

## Request

```json
{
  "cmd": "users_banned_list"
}
```

### Fields

None.

## Response

### On Success

```json
{
  "cmd": "users_banned_list",
  "users": ["username1", "username2", "username3"]
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`

## Notes

- Requires `owner` role.
- Returns a list of usernames (not user IDs).
- Banned users are those with the `banned` role.
- Banned users cannot authenticate with the server.
- Currently connected banned users will remain connected until they disconnect.
- Empty list is returned if no users are banned.
- Use `user_unban` to remove a user from the banned list.
- Use `user_ban` to add a user to the banned list.

## See Also

- [user_ban](user_ban.md) - Ban a user
- [user_unban](user_unban.md) - Unban a user
- [users_list](users_list.md) - List all users

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "users_banned_list":`).
