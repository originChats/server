# Config Structure

The server configuration (`config.json`) controls global settings, limits, and features for OriginChats.

Example config snippet:

```json
{
  "limits": {
    "post_content": 2000,
    "search_results": 30
  },
  "uploads": {
    "emoji_allowed_file_types": ["gif", "jpg", "jpeg"]
  }
}
```

- `limits.post_content`: Maximum message length.
- `limits.search_results`: Maximum number of search results returned by `messages_search`.
- `uploads.emoji_allowed_file_types`: Allowed custom emoji upload extensions.

See your server's `config.json` for all available options.
