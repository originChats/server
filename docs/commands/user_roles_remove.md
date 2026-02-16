# Command: user_roles_remove

Remove roles from a user (owner only).

## Request

```json
{
  "cmd": "user_roles_remove",
  "user": "username_or_id",
  "roles": ["admin", "moderator"]
}
```

### Fields

- `user`: (required) Username or user ID of the target user.
- `roles`: (required) Array of role names to remove from the user.

## Response

### On Success

```json
{
  "cmd": "user_roles_remove",
  "user": "username",
  "roles": ["user"],
  "removed": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "User parameter is required"}`
- `{"cmd": "error", "val": "Roles list is required"}`
- `{"cmd": "error", "val": "User not found"}`
- `{"cmd": "error", "val": "Cannot remove all roles from a user"}`

## Notes

- Requires `owner` role.
- Can remove one or multiple roles in a single request.
- A user must have at least one role at all times.
- Roles that the user doesn't have are ignored.
- Usernames are case-insensitive for lookup.
- Role changes take effect immediately for all future actions by the user.
- The user's role color will update to match their remaining highest-priority role.
- If all roles would be removed, the command fails and no changes are made.

## See Also

- [user_roles_add](user_roles_add.md) - Add roles to a user
- [user_roles_get](user_roles_get.md) - Get a user's roles
- [user_ban](user_ban.md) - Ban a user

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_roles_remove":`).
