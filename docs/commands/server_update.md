# Command: server_update

Update the server's display information (owner only).

## Request

```json
{
  "cmd": "server_update",
  "name": "My Server Name",
  "icon": "https://example.com/icon.png",
  "banner": "https://example.com/banner.png"
}
```

### Fields

- `name`: (optional) New server name. Pass `null` to clear.
- `icon`: (optional) URL or filename for the server icon. Pass `null` to clear.
- `banner`: (optional) URL or filename for the server banner. Pass `null` to clear.

At least one field must be provided.

## Response

### On Success

Broadcast to all connected clients:

```json
{
  "cmd": "server_update",
  "name": "My Server Name",
  "icon": "https://example.com/icon.png",
  "banner": "https://example.com/banner.png"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Server data not available"}`
- `{"cmd": "error", "val": "Name must be a string or null"}`
- `{"cmd": "error", "val": "Icon must be a string or null"}`
- `{"cmd": "error", "val": "Banner must be a string or null"}`
- `{"cmd": "error", "val": "No updates provided"}`

## Notes

- Requires `owner` role.
- All fields are optional, but at least one must be provided.
- Passing `null` for a field clears/removes that value.
- Changes are broadcast to all connected clients immediately.
- For local files, place them in `db/serverAssets/` and use just the filename.

## See Also

- [server_info](server_info.md) - Get server info
- [channel_update](channel_update.md) - Update a channel
- [role_update](role_update.md) - Update a role

See implementation: [`handlers/messages/server.py`](../../handlers/messages/server.py).
