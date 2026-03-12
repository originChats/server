# Command: push_unsubscribe

Remove a Web Push subscription for the authenticated user. After this call the server will no longer send push notifications to the specified endpoint.

## Request

```json
{
  "cmd": "push_unsubscribe",
  "endpoint": "https://fcm.googleapis.com/fcm/send/abc123..."
}
```

### Fields

- `endpoint` *(string, required)*: The push service URL that was used when the subscription was registered with `push_subscribe`. This is the same value as `subscription.endpoint` from the browser's `PushManager`.

## Response

### On Success

```json
{ "cmd": "push_unsubscribed", "success": true }
```

### On Error

```json
{ "cmd": "error", "src": "push_unsubscribe", "val": "<reason>" }
```

Common reasons:

| Message | Cause |
|---------|-------|
| `"Not authenticated"` | WebSocket session is not authenticated |
| `"Missing endpoint"` | `endpoint` field absent or empty |
| `"Failed to remove subscription"` | Server-side I/O error |

## Notes

- The user must be authenticated.
- The deletion is **scoped to the authenticated user** — a user cannot remove another user's subscription even if they know the endpoint URL.
- If the endpoint is not found in storage (e.g. it was already removed), the call succeeds silently.
- The response is sent **only to the requesting client** (not broadcast).
- Calling `PushManager.unsubscribe()` in the browser does **not** automatically notify the server. Clients should explicitly send `push_unsubscribe` when the user opts out of push notifications.

## Usage Example

```javascript
async function disablePush(ws) {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();

  if (!subscription) {
    console.log("No active push subscription.");
    return;
  }

  // Unsubscribe in the browser
  await subscription.unsubscribe();

  // Notify the server so it stops sending pushes
  ws.send(JSON.stringify({
    cmd: "push_unsubscribe",
    endpoint: subscription.endpoint,
  }));
}

ws.addEventListener("message", (event) => {
  const data = JSON.parse(event.data);
  if (data.cmd === "push_unsubscribed" && data.success) {
    console.log("Push notifications disabled.");
  }
});
```

## Related Commands

- [push_get_vapid](push_get_vapid.md) — Fetch the server's VAPID public key
- [push_subscribe](push_subscribe.md) — Register a push subscription

See also: [Web Push Notifications guide](../push_notifications.md)

See implementation: [`handlers/push.py`](../../handlers/push.py) (`handle_push_unsubscribe`).
