# Command: emoji_get_id

Resolve an emoji name to its ID (owner only).

## Request

```json
{
  "cmd": "emoji_get_id",
  "name": "defaultHUH"
}
```

### Fields

- `name`: (required) Emoji name.

## Response

### On Success

```json
{
  "cmd": "emoji_get_id",
  "name": "defaultHUH",
  "id": "0"
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Emoji not found"}`
- `{"cmd": "error", "val": "Invalid emoji_get_id command scheme: ..."}` - When validation fails

## Notes

- Requires `owner` role.
- IDs are returned as strings.

## See Also

- [emoji_get_filename](emoji_get_filename.md) - Resolve emoji name to file path
- [emoji_get_all](emoji_get_all.md) - List all emojis

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "emoji_get_id":`).
