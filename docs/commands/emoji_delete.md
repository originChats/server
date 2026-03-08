# Command: emoji_delete

Delete a custom server emoji by ID (owner only).

## Request

```json
{
  "cmd": "emoji_delete",
  "emoji_id": 0
}
```

### Fields

- `emoji_id`: (required) Numeric emoji ID.

## Response

### On Success

```json
{
  "cmd": "emoji_delete",
  "id": 0,
  "deleted": true
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Invalid emoji_delete command scheme: ..."}` - When validation fails

## Notes

- Requires `owner` role.
- `deleted` is `false` if the ID does not exist.

## See Also

- [emoji_add](emoji_add.md) - Add a new emoji
- [emoji_get_all](emoji_get_all.md) - List all emojis

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "emoji_delete":`).
