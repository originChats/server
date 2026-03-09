# Command: messages_search

**Request:**
```json
{
  "cmd": "messages_search",
  "channel": "<channel_name>",
  "query": "<query>"
}
```

- `channel`: Channel name.
- `query`: Search query.

**Response:**
- On success:
```json
{
  "cmd": "messages_search",
  "channel": "<channel_name>",
  "query": "<query>",
  "results": [ ...array of message objects... ]
}
```
- On error: see [common errors](errors.md).

**Notes:**
- User must be authenticated and have access to the channel.
- Result count is capped by `config.json` at `limits.search_results`.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "messages_search":`).
