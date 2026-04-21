# Command: modlog_summary

Get aggregated statistics from the audit log.

## Request

```json
{
  "cmd": "modlog_summary"
}
```

No parameters required.

## Response

```json
{
  "cmd": "modlog_summary",
  "action_counts": {
    "user_moderation.user_ban": 15,
    "user_moderation.user_unban": 8,
    "role_management.role_create": 5,
    "message_moderation.message_delete": 45,
    "server_management.emoji_add": 7
  },
  "category_totals": {
    "user_moderation": 46,
    "role_management": 17,
    "message_moderation": 45,
    "server_management": 7
  },
  "total": 119
}
```

### Fields

- `action_counts`: `{category.action: count}` - specific action frequencies
- `category_totals`: `{category: count}` - totals per category
- `total`: Total entries analyzed (most recent 10,000)

### Error

```json
{"cmd": "error", "val": "Access denied: 'view_audit_log' or 'manage_users' permission required"}
```

## Categories

- `user_moderation` - Bans, unbans, timeouts, role changes
- `role_management` - Role creation, updates, permissions
- `channel_management` - Channel changes
- `message_moderation` - Message deletion, pinning
- `server_management` - Server settings, emojis, webhooks

## Use Cases

### Activity overview

Quick gauge of moderation activity:
- High `user_moderation` count = active moderation
- High `message_moderation` count = possible spam/spike

### Dashboard metrics

```javascript
const summary = await sendCommand({cmd: "modlog_summary"});

dashboard.show({
  totalActions: summary.total,
  bansThisWeek: summary.action_counts["user_moderation.user_ban"] || 0,
  topCategory: getTopCategory(summary.category_totals),
  moderationEffort: summary.category_totals.user_moderation || 0
});
```

### Trend comparison

Store and compare summaries over time:

```javascript
const current = await sendCommand({cmd: "modlog_summary"});
const previous = loadStoredSummary();

const newBans = (current.action_counts["user_moderation.user_ban"] || 0) -
                (previous?.action_counts["user_moderation.user_ban"] || 0);
```

## Permissions

- Requires authentication
- Requires `view_audit_log` or `manage_users` permission

## Notes

- Analyzes up to 10,000 most recent entries
- No pagination - single request
- Complement with `modlog_get` for detailed entries

See implementation: [`handlers/messages/modlog.py`](../../handlers/messages/modlog.py)
