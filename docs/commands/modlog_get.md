# Command: modlog_get

Retrieve audit log entries with optional filtering and pagination.

## Request

```json
{
  "cmd": "modlog_get",
  "limit": 100,
  "offset": 0,
  "after": 1234567890.123,
  "category": "user_moderation",
  "actor": "user-uuid",
  "target": "target-uuid",
  "action": "user_ban"
}
```

### Parameters

All parameters optional:

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max entries to return (1-200, default: 100) |
| `offset` | int | Skip N entries for pagination (default: 0) |
| `after` | float | Unix timestamp - only return entries newer than this time |
| `category` | string | Filter by category (e.g., "user_moderation") |
| `actor` | string | Filter by actor user ID |
| `target` | string | Filter by target user ID |
| `action` | string | Filter by specific action (e.g., "user_ban") |

## Response

### Success

```json
{
  "cmd": "modlog_get",
  "entries": [
    {
      "id": "1713648900123-user-uuid",
      "action": "user_ban",
      "category": "user_moderation",
      "actor_id": "user-uuid",
      "actor_name": "AdminUser",
      "target_id": "target-uuid",
      "target_name": "BannedUser",
      "details": "Spamming",
      "timestamp": 1713648900.123
    }
  ],
  "total": 150,
  "offset": 0,
  "limit": 100
}
```

### Entry Fields

- `id`: Unique ID (timestamp-actor_id)
- `action`: What happened (e.g., "user_ban", "role_create")
- `category`: Action category
- `actor_id`, `actor_name`: Who did it
- `target_id`, `target_name`: Who it was done to (if any)
- `details`: Additional info (varies by action)
- `timestamp`: When it happened (Unix)

### Error

```json
{"cmd": "error", "val": "Access denied: 'view_audit_log' or 'manage_users' permission required"}
```

## Get Recent Actions

Use the `after` parameter with a timestamp to fetch only recent entries.

### Last 24 hours

```javascript
const oneDayAgo = Date.now() / 1000 - 86400;

{
  "cmd": "modlog_get",
  "after": oneDayAgo,
  "limit": 100
}
```

### Last 7 days

```javascript
const oneWeekAgo = Date.now() / 1000 - (7 * 86400);

{
  "cmd": "modlog_get",
  "after": oneWeekAgo,
  "limit": 100
}
```

### Recent channel activity

```json
{
  "cmd": "modlog_get",
  "category": "channel_management",
  "after": 1713640000.000
}
```

## Categories & Actions

| Category | Actions |
|----------|---------|
| `user_moderation` | user_ban, user_unban, user_timeout, user_roles_set, user_update |
| `role_management` | role_create, role_update, role_delete, role_reorder, role_permissions_set |
| `channel_management` | channel_create, channel_update, channel_move, channel_delete |
| `message_moderation` | message_delete, message_pin, message_unpin |
| `server_management` | server_update, emoji_add/update/delete, webhook_create/update/delete |

## Examples

### Recent moderation actions

```json
{
  "cmd": "modlog_get",
  "category": "user_moderation",
  "after": 1713571200.000
}
```

### Actions by a specific admin

```json
{
  "cmd": "modlog_get",
  "actor": "admin-user-uuid",
  "limit": 50
}
```

### Actions affecting a specific user

```json
{
  "cmd": "modlog_get",
  "target": "user-uuid",
  "limit": 50
}
```

### Pagination

```json
{
  "cmd": "modlog_get",
  "limit": 50,
  "offset": 50
}
```

## Permissions

- Requires authentication
- Requires `view_audit_log` or `manage_users` permission

## Notes

- Results ordered newest first (by timestamp)
- `total` is count before pagination
- Old entries auto-expire based on category retention settings
- Multiple filters combine with AND logic

See [modlog_summary](modlog_summary.md) for aggregated stats.

See implementation: [`handlers/messages/modlog.py`](../../handlers/messages/modlog.py)
