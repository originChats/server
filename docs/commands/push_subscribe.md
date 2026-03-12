# Command: push_subscribe

Register a Web Push subscription for the authenticated user. The server stores the subscription and uses it to deliver push notifications when the user is offline (no active WebSocket connection).

## Request

```json
{
  "cmd": "push_subscribe",
  "subscription": {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
    "keys": {
      "p256dh": "BNcRdreALRFXTkOOUHK...",
      "auth":   "tBHItJI5svbpez7KI4..."
    }
  }
}
```

### Fields

- `subscription` *(object, required)*: The push subscription object returned by the browser's `PushManager.subscribe()` call.
  - `endpoint` *(string, required)*: The push service URL provided by the browser vendor (Chrome, Firefox, etc.). Unique per browser/device.
  - `keys.p256dh` *(string, required)*: The client's elliptic-curve public key (base64url). Used to encrypt the push payload.
  - `keys.auth` *(string, required)*: A 16-byte authentication secret (base64url). Used together with `p256dh` to encrypt payloads end-to-end.

The easiest way to obtain these values is:

```javascript
const registration = await navigator.serviceWorker.ready;
const subscription = await registration.pushManager.subscribe({ ... });
const json = subscription.toJSON();
// json.endpoint, json.keys.p256dh, json.keys.auth
```

## Response

### On Success

```json
{ "cmd": "push_subscribed", "success": true }
```

### On Error

```json
{ "cmd": "error", "src": "push_subscribe", "val": "<reason>" }
```

Common reasons:

| Message | Cause |
|---------|-------|
| `"Not authenticated"` | WebSocket session is not authenticated |
| `"Missing subscription object"` | `subscription` field absent or not an object |
| `"subscription must include endpoint, keys.p256dh and keys.auth"` | One or more required sub-fields are missing |
| `"Failed to save subscription"` | Server-side I/O error writing to `db/push_subscriptions.json` |

## Notes

- The user must be authenticated. Unauthenticated subscription attempts are rejected.
- **Upsert behaviour**: if a subscription with the same `endpoint` already exists (e.g. the browser re-subscribed), the stored record is updated. No duplicates are created.
- A single user may have multiple active subscriptions — one per browser/device. All stored subscriptions receive notifications when the user is offline.
- Subscriptions that are rejected by the push service with HTTP `404` or `410` are automatically purged by the server the next time a push is sent to them.
- The response is sent **only to the requesting client** (not broadcast).

## Usage Example

```javascript
async function registerPush(ws) {
  // Step 1: get the server's VAPID public key
  ws.send(JSON.stringify({ cmd: "push_get_vapid" }));
}

ws.addEventListener("message", async (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === "push_vapid") {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(data.key),
    });

    // Step 2: register the subscription with the server
    ws.send(JSON.stringify({
      cmd: "push_subscribe",
      subscription: subscription.toJSON(),
    }));
  }

  if (data.cmd === "push_subscribed" && data.success) {
    console.log("Push notifications enabled.");
  }
});

// Convert base64url string to Uint8Array for PushManager
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}
```

## Related Commands

- [push_get_vapid](push_get_vapid.md) — Fetch the server's VAPID public key (required before subscribing)
- [push_unsubscribe](push_unsubscribe.md) — Remove a push subscription

See also: [Web Push Notifications guide](../push_notifications.md)

See implementation: [`handlers/push.py`](../../handlers/push.py) (`handle_push_subscribe`).
