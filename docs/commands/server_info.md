# Command: server_info

Get the server's display information.

## Request

```json
{
  "cmd": "server_info"
}
```

## Response

### On Success

```json
{
  "cmd": "server_info",
  "name": "My Server Name",
  "icon": "https://example.com/icon.png",
  "banner": "https://example.com/banner.png"
}
```

## Notes

- No authentication required.
- Returns the current server name, icon, and banner URLs.

## See Also

- [server_update](server_update.md) - Update server info (owner only)

See implementation: [`handlers/messages/server.py`](../../handlers/messages/server.py).
