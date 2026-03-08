# Command: emoji_get_filename

Resolve an emoji name to its stored file path (owner only).

## Request

```json
{
  "cmd": "emoji_get_filename",
  "name": "defaultHUH"
}
```

### Fields

- `name`: (required) Emoji name.

## Response

### On Success

```json
{
  "cmd": "emoji_get_filename",
  "name": "defaultHUH",
  "filepath": "/absolute/path/to/db/serverEmojis/0.svg"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Emoji not found"}`
- `{"cmd": "error", "val": "Emoji file not found"}`
- `{"cmd": "error", "val": "Invalid emoji_get_filename command scheme: ..."}` - When validation fails

## Notes

- Requires `owner` role.
- Returns server filesystem path, not a public URL.

## See Also

- [emoji_get_id](emoji_get_id.md) - Resolve emoji name to ID
- [emoji_get_all](emoji_get_all.md) - List all emojis

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "emoji_get_filename":`).
