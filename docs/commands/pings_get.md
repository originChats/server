# Command: pings_get

Get messages where the requesting user was mentioned (@username or @&rolename) or replied to across all accessible channels.

## Request

```json
{
  "cmd": "pings_get",
  "limit": 50,
  "offset": 0
}
```

### Fields

- `limit`: (optional, default: `50`) Number of messages to return. Must be between 1 and 100.
- `offset`: (optional, default: `0`) Number of messages to skip. Used for pagination.

## Response

### On Success

```json
{
  "cmd": "pings_get",
  "messages": [
    {
      "id": "message-uuid",
      "user": "sender_username",
      "content": "Hey @john can you check this?",
      "timestamp": 1773182676.073865,
      "type": "message",
      "pinned": false,
      "channel": "general"
    },
    {
      "id": "message-uuid-2",
      "user": "alice",
      "content": "Sure, I can help with that!",
      "timestamp": 1773182000.123456,
      "type": "message",
      "pinned": false,
      "reply_to": {
        "id": "original-message-id",
        "user": "bob"
      },
      "channel": "general"
    },
    {
      "id": "message-uuid-3",
      "user": "moderator_bot",
      "content": "@&admin update everyone on the status",
      "timestamp": 1773181000.789012,
      "type": "message",
      "pinned": false,
      "channel": "announcements"
    }
  ],
  "offset": 0,
  "limit": 50,
  "total": 150
}
```

### Response Fields

- `messages`: Array of messages where the user was pinged or replied to
  - Each message includes all standard message fields plus `channel` to indicate which channel it's from
  - If a reply, includes `reply_to` with the original message info
- `offset`: The offset used for this request
- `limit`: The limit used for this request
- `total`: Total number of pinged messages matching the criteria (for pagination info)

## Error Responses

- `{"cmd": "error", "val": "Authentication required"}`
- `{"cmd": "error", "val": "User not found"}`
- `{"cmd": "error", "val": "Limit must be a number between 1 and 100"}`
- `{"cmd": "error", "val": "Offset must be a non-negative number"}`

## Notes

- User must be authenticated.
- Searches across **all text channels** the user has view permission for.
- Finds messages with:
  - **Direct mentions**: `@username` patterns
  - **Role mentions**: `@&rolename` patterns (if user has that role)
  - **Replies**: Messages replying to a message you sent (unless `ping: false` was set)
- Messages are returned in **descending order by timestamp** (newest first).
- Only messages in channels the user can view are returned.
- The response is **not global** - sent only to the requesting client.

## Ping Patterns

The search matches these patterns:

### Direct User Mentions
- `@username` - e.g., `@alice help me`
- `@username@` - e.g., `@alice@ check this out`
- `@username ` (with space) - e.g., `@alice hello`

### Role Mentions
For each role the user has:
- `@&rolename` - e.g., `@&admin meeting in 5`
- `@&rolename@` - e.g., `@&moderators@ please review`
- `@&rolename ` (with space) - e.g., `@&devs new deploy`

### Replies
- Messages that have a `reply_to` field pointing to a message you authored
- Respects the `ping` field on the reply message:
  - If `ping` is `true` or not present (defaults to `true`), the reply counts as a ping
  - If `ping` is `false`, the reply will NOT count as a ping for `pings_get`

The `ping` field allows users to reply to someone without notifying them. This is useful for:

- **Follow-up messages**: When you want to continue a conversation without pinging the original author
- **Personal notes**: When replying to yourself for organization purposes
- **Silent acknowledgments**: When you want to acknowledge a message without triggering a notification

Example:

```javascript
// Regular reply - will ping @bob
ws.send(JSON.stringify({
  cmd: "message_new",
  channel: "general",
  content: "Sure, I can help!",
  reply_to: "message-id"
  // ping: true (default) - this will appear in bob's pings_get
}));

// Silent reply - will NOT ping @bob
ws.send(JSON.stringify({
  cmd: "message_new",
  channel: "general",
  content: "Thanks for the info",
  reply_to: "message-id",
  ping: false
  // bob won't see this in their pings_get
}));
```

```javascript
// Regular reply - will ping/bob
ws.send(JSON.stringify({
  cmd: "message_new",
  channel: "general",
  content: "Sure, I can help!",
  reply_to: "message-id"
}));

// Silent reply - will NOT ping
ws.send(JSON.stringify({
  cmd: "message_new",
  channel: "general",
  content: "Thanks for the info",
  reply_to: "message-id",
  ping: false
}));
```

## Pagination

Used to navigate through large sets of pinged messages:

```javascript
// First page
ws.send(JSON.stringify({
  cmd: "pings_get",
  limit: 50,
  offset: 0
}));

// Second page
ws.send(JSON.stringify({
  cmd: "pings_get",
  limit: 50,
  offset: 50
}));

// Next page calculation
function getNextPage(offset, limit) {
  return {
    cmd: "pings_get",
    limit: limit,
    offset: offset + limit
  };
}
```

## Usage Examples

### Basic Fetch

```json
{
  "cmd": "pings_get"
}
```

Returns the first 50 messages with pings.

### With Custom Limit

```json
{
  "cmd": "pings_get",
  "limit": 100
}
```

Returns the first 100 messages (max allowed).

### With Pagination

```json
{
  "cmd": "pings_get",
  "limit": 20,
  "offset": 40
}
```

Returns messages 41-60 (skipping the first 40).

## Client-Side Handling

### Basic Implementation

```javascript
function fetchPings(offset = 0, limit = 50) {
  ws.send(JSON.stringify({
    cmd: "pings_get",
    limit: limit,
    offset: offset
  }));
}

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'pings_get') {
    console.log(`Found ${data.messages.length} pings (total: ${data.total})`);
    data.messages.forEach(msg => {
      console.log(`[${msg.channel}] ${msg.user}: ${msg.content}`);
    });

    // Show load more button if there are more pings
    const hasMore = data.offset + data.messages.length < data.total;
    if (hasMore) {
      showLoadMoreButton();
    }
  }
};
```

### Displaying Pings

```javascript
function renderPings(pingsData) {
  const container = document.getElementById('pings-container');
  container.innerHTML = '';

  if (pingsData.messages.length === 0) {
    container.innerHTML = '<p>No pings found</p>';
    return;
  }

  pingsData.messages.forEach(msg => {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message ping';
    msgDiv.innerHTML = `
      <div class="meta">
        <span class="channel">#${msg.channel}</span>
        <span class="time">${new Date(msg.timestamp * 1000).toLocaleString()}</span>
      </div>
      <div class="content">
        <span class="username">${msg.user}:</span>
        ${formatContent(msg.content)}
      </div>
    `;
    container.appendChild(msgDiv);
  });
}

function formatContent(content) {
  // Highlight mentions
  return content
    .replace(/@([a-zA-Z0-9_]+)/g, '<span class="mention user">@$1</span>')
    .replace(/@&([a-zA-Z0-9_]+)/g, '<span class="mention role">@$&$1</span>');
}
```

### Pagination Widget

```javascript
class PingsPagination {
  constructor(ws) {
    this.ws = ws;
    this.offset = 0;
    this.limit = 50;
    this.total = 0;
  }

  fetchPings() {
    this.ws.send(JSON.stringify({
      cmd: "pings_get",
      limit: this.limit,
      offset: this.offset
    }));
  }

  nextPage() {
    if (this.offset + this.limit < this.total) {
      this.offset += this.limit;
      this.fetchPings();
    }
  }

  previousPage() {
    if (this.offset > 0) {
      this.offset = Math.max(0, this.offset - this.limit);
      this.fetchPings();
    }
  }

  goToPage(pageNumber) {
    this.offset = (pageNumber - 1) * this.limit;
    this.fetchPings();
  }

  getCurrentPageNumber() {
    return Math.floor(this.offset / this.limit) + 1;
  }

  getTotalPages() {
    return Math.ceil(this.total / this.limit);
  }

  hasPreviousPage() {
    return this.offset > 0;
  }

  hasNextPage() {
    return this.offset + this.limit < this.total;
  }
}

// Usage
const pingsPagination = new PingsPagination(ws);

// UI handlers
document.getElementById('next-page').addEventListener('click', () => {
  pingsPagination.nextPage();
});

document.getElementById('prev-page').addEventListener('click', () => {
  pingsPagination.previousPage();
});
```

## Performance Considerations

- This command searches through all accessible channels, which may be resource-intensive for large servers.
- Consider the following optimizations:
  - Cache the results and update incrementally
  - Use a reasonable limit (default 50 is good)
  - Don't fetch too frequently
  - Consider using WebSocket events to notify users of new pings instead of polling

## Related Commands

- [messages_get](messages_get.md) - Get messages from a specific channel
- [messages_search](messages_search.md) - Search messages in a channel
- [channels_get](channels_get.md) - Get list of available channels

See implementation: [`handlers/message.py`](../../handlers/message.py) (search for `case "pings_get":`).
