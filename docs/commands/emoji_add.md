# Command: emoji_add

Add a custom server emoji (owner only).

## Request

```json
{
  "cmd": "emoji_add",
  "name": "defaultHUH",
  "image": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iLi4uIj4uLi48L3N2Zz4="
}
```

### Fields

- `name`: (required) Emoji name. Must match server validation rules.
- `image`: (required) Base64 image data URI (`gif`, `jpg`, `jpeg`, `svg`).

## Response

### On Success

```json
{
  "cmd": "emoji_add",
  "id": "0",
  "added": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Error adding emoji"}`
- `{"cmd": "error", "val": "Invalid emoji_add command scheme: ..."}` - When validation fails

## Notes

- Requires `owner` role.
- Emoji names must be unique.
- Image type must be one of server-allowed file types.

## See Also

- [emoji_delete](emoji_delete.md) - Delete an emoji
- [emoji_update](emoji_update.md) - Update emoji name/file reference
- [emoji_get_all](emoji_get_all.md) - List all emojis

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "emoji_add":`).
