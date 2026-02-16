# Command: role_create

Create a new role (owner only).

## Request

```json
{
  "cmd": "role_create",
  "name": "role_name",
  "description": "Optional role description",
  "color": "#FF0000"
}
```

### Fields

- `name`: (required) The name of the new role. Must be unique.
- `description`: (optional) A description of the role.
- `color`: (optional) Hex color code for the role (e.g., "#FF0000").

## Response

### On Success

```json
{
  "cmd": "role_create",
  "name": "role_name",
  "created": true
}
```

### On Failure

If the role already exists:

```json
{
  "cmd": "error",
  "src": "role_create",
  "val": "Role already exists"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Role name is required"}`
- `{"cmd": "error", "val": "Role already exists"}`

## Notes

- Requires `owner` role.
- Role names are case-sensitive.
- Role names cannot be the same as existing roles.
- The role is created with no users assigned - use `user_roles_add` to assign it to users.
- The role can be used in channel permissions immediately after creation.

## See Also

- [role_update](role_update.md) - Update an existing role
- [role_delete](role_delete.md) - Delete a role
- [role_list](role_list.md) - List all roles
- [user_roles_add](user_roles_add.md) - Add roles to a user

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "role_create":`).
