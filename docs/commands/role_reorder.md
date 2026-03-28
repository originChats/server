# Command: role_reorder

Reorder all roles by providing a new order (owner only).

## Request

```json
{
  "cmd": "role_reorder",
  "roles": ["owner", "admin", "moderator", "user"]
}
```

### Fields

- `roles`: (required) Array of role names in the desired order. All existing roles must be included.

## Response

### On Success

Broadcast to all connected clients:

```json
{
  "cmd": "roles_list",
  "roles": {
    "owner": {...},
    "admin": {...},
    "moderator": {...},
    "user": {...}
  }
}
```

Returns to the requester:

```json
{
  "cmd": "role_reorder",
  "roles": ["owner", "admin", "moderator", "user"]
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Server data not available"}`
- `{"cmd": "error", "val": "Roles array is required"}`
- `{"cmd": "error", "val": "Failed to reorder roles"}`

## Notes

- Requires `owner` role.
- All existing roles must be included in the reorder array.
- The order determines how roles are displayed and their priority.
- Roles are returned in order by `roles_list` after reordering.

## See Also

- [roles_list](roles_list.md) - List all roles
- [role_create](role_create.md) - Create a role
- [role_update](role_update.md) - Update a role
- [role_delete](role_delete.md) - Delete a role

See implementation: [`handlers/messages/role.py`](../../handlers/messages/role.py).
