# Command: role_update

Update an existing role's properties (owner only).

## Request

```json
{
  "cmd": "role_update",
  "name": "role_name",
  "description": "Updated description",
  "color": "#00FF00"
}
```

### Fields

- `name`: (required) The name of the role to update.
- `description`: (optional) New description for the role. If omitted, description is unchanged.
- `color`: (optional) New hex color code for the role. If omitted, color is unchanged.

## Response

### On Success

```json
{
  "cmd": "role_update",
  "name": "role_name",
  "updated": true
}
```

### On Failure

```json
{
  "cmd": "error",
  "src": "role_update",
  "val": "Role not found"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Role name is required"}`
- `{"cmd": "error", "val": "Role not found"}`

## Notes

- Requires `owner` role.
- Updates are applied to the role immediately.
- Changes to role color will be reflected for all users who have this role.
- Changes to role description are informational only.
- Cannot rename a role - use `role_delete` and `role_create` to rename.

## See Also

- [role_create](role_create.md) - Create a new role
- [role_delete](role_delete.md) - Delete a role
- [role_list](role_list.md) - List all roles

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "role_update":`).
