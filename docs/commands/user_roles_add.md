# Command: user_roles_add

Add roles to a user (owner only).

## Request

```json
{
  "cmd": "user_roles_add",
  "user": "username_or_id",
  "roles": ["admin", "moderator"]
}
```

### Fields

- `user`: (required) Username or user ID of the target user.
- `roles`: (required) Array of role names to add to the user.

## Response

### On Success

```json
{
  "cmd": "user_roles_add",
  "user": "username",
  "roles": ["admin", "moderator", "user"],
  "added": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "User parameter is required"}`
- `{"cmd": "error", "val": "Roles list is required"}`
- `{"cmd": "error", "val": "User not found"}`
- `{"cmd": "error", "val": "Role 'role_name' does not exist"}`

## Notes

- Requires `owner` role.
- Can add one or multiple roles in a single request.
- Roles are added to the beginning of the user's role list.
- Roles that the user already has are ignored (no duplicate roles).
- All roles must exist before being added to a user.
- Usernames are case-insensitive for lookup but are stored as provided during registration.
- New roles take effect immediately for all future actions by the user.
- The user's role color will update to match their highest-priority role (first in list).

## See Also

- [user_roles_remove](user_roles_remove.md) - Remove roles from a user
- [user_roles_get](user_roles_get.md) - Get a user's roles
- [role_create](role_create.md) - Create a new role
- [user_ban](user_ban.md) - Ban a user

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "user_roles_add":`).
