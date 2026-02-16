# Command: role_delete

Delete a role from the server (owner only).

## Request

```json
{
  "cmd": "role_delete",
  "name": "role_name"
}
```

### Fields

- `name`: (required) The name of the role to delete.

## Response

### On Success

```json
{
  "cmd": "role_delete",
  "name": "role_name",
  "deleted": true
}
```

### On Failure

```json
{
  "cmd": "error",
  "src": "role_delete",
  "val": "Role is assigned to user 'username'"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Role name is required"}`
- `{"cmd": "error", "val": "Role not found"}`
- `{"cmd": "error", "val": "Cannot delete system roles"}`
- `{"cmd": "error", "val": "Role is assigned to user 'username'"}` - Role must be removed from all users first
- `{"cmd": "error", "val": "Role is used in channel 'channel_name' permissions"}` - Role must be removed from all channel permissions first

## Notes

- Requires `owner` role.
- Cannot delete system roles: `owner`, `admin`, `user`.
- The role must be removed from all users before deletion (use `user_roles_remove`).
- The role must be removed from all channel permissions before deletion.
- Use `user_roles_remove` to remove the role from users.
- Use `channel_update` to remove the role from channel permissions.

## See Also

- [role_create](role_create.md) - Create a new role
- [role_update](role_update.md) - Update an existing role
- [role_list](role_list.md) - List all roles
- [user_roles_remove](user_roles_remove.md) - Remove roles from a user

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "role_delete":`).
