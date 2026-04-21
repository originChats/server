from db import modlog, permissions as perms
from handlers.messages.helpers import _error, _require_user_id


def _check_access(user_id, match_cmd):
    if perms.has_permission(user_id, "view_audit_log"):
        return None
    if perms.has_permission(user_id, "manage_users"):
        return None
    return _error("Access denied: 'view_audit_log' or 'manage_users' permission required", match_cmd)


def handle_modlog_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    error = _check_access(user_id, match_cmd)
    if error:
        return error

    limit = message.get("limit", 100)
    offset = message.get("offset", 0)

    if not isinstance(limit, int) or limit < 1 or limit > 200:
        return _error("Limit must be between 1 and 200", match_cmd)
    if not isinstance(offset, int) or offset < 0:
        return _error("Offset must be a non-negative integer", match_cmd)

    after = message.get("after")
    if after is not None:
        try:
            after = float(after)
        except (ValueError, TypeError):
            return _error("After must be a valid Unix timestamp", match_cmd)

    result = modlog.get_log(
        category=message.get("category"),
        actor_id=message.get("actor"),
        target_id=message.get("target"),
        action=message.get("action"),
        limit=limit,
        offset=offset,
        after=after,
    )

    return {"cmd": "modlog_get", **result}


def handle_modlog_summary(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    error = _check_access(user_id, match_cmd)
    if error:
        return error

    result = modlog.get_log(limit=10000)
    entries = result["entries"]

    summary = {}
    for entry in entries:
        cat = entry.get("category", "other")
        act = entry.get("action", "unknown")
        key = f"{cat}.{act}"
        summary[key] = summary.get(key, 0) + 1

    category_totals = {}
    for entry in entries:
        cat = entry.get("category", "other")
        category_totals[cat] = category_totals.get(cat, 0) + 1

    return {
        "cmd": "modlog_summary",
        "action_counts": summary,
        "category_totals": category_totals,
        "total": result["total"],
    }
