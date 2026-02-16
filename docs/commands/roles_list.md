# Command: roles_list

List all roles on the server (owner only).

## Request

```json
{
  "cmd": "roles_list"
}
```

### Fields

None.

## Response

### On Success

```json
{
  "cmd": "roles_list",
  "roles": {
    "owner": {
      "description": "Owns the server so has all the perms fr",
      "color": "#FF00FF"
    },
    "admin": {
      "description": "Administrator role with full permissions.",
      "color": "#FF0000"
    }
  }
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`

## Notes

- Requires `owner` role.
- Returns all roles as a dictionary keyed by role name.
- Each role object contains:
  - `description`: Role description (optional)
  - `color`: Hex color code (optional)

## See Also

- [role_create](role_create.md) - Create a new role
- [role_update](role_update.md) - Update an existing role
- [role_delete](role_delete.md) - Delete a role

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "roles_list":`).
