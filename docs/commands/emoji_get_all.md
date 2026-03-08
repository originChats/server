# Command: emoji_get_all

Return all custom server emojis (owner only).

## Request

```json
{
  "cmd": "emoji_get_all"
}
```

## Response

### On Success

```json
{
  "cmd": "emoji_get_all",
  "emojis": {
    "0": {
      "name": "defaultHUH",
      "fileName": "0.svg"
    }
  }
}
```

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "Access denied: owner role required"}`
- `{"cmd": "error", "val": "Invalid emoji_get_all command scheme: ..."}` - When validation fails

## Notes

- Requires `owner` role.
- Response keys are emoji IDs as strings.

## See Also

- [emoji_get_id](emoji_get_id.md) - Resolve emoji name to ID
- [emoji_get_filename](emoji_get_filename.md) - Resolve emoji name to filepath

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "emoji_get_all":`).
