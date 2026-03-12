# Command: push_get_vapid

Request the server's VAPID public key so the client can subscribe to Web Push notifications via the browser's `PushManager` API.

## Request

```json
{
  "cmd": "push_get_vapid"
}
```

No additional fields are required.

## Response

### On Success

```json
{
  "cmd": "push_vapid",
  "key": "BH56TzQe4dAmwvhwsfxB6ZlSNgNaVaoZI4aTKnqen8axN2x-BmuIcTsZsNzkmO2eaq9fM0Vv89iIpG0-LdBrXDg"
}
```

### Response Fields

- `key`: Base64url-encoded uncompressed VAPID public key. Must be converted to a `Uint8Array` before passing to `PushManager.subscribe()` as `applicationServerKey` (see usage example below).

### On Error

```json
{ "cmd": "error", "src": "push_get_vapid", "val": "VAPID keys not configured on this server" }
```

Returned when the server has not been set up with a VAPID key pair (see [Push Notifications setup guide](../push_notifications.md)).

## Notes

- The user must be authenticated before sending this command.
- The public key is stable — it does not change between server restarts. Clients may cache it, but re-fetching on each subscription attempt is fine.
- This command does not modify any server state.

## Usage Example

```javascript
// 1. Ask the server for its VAPID public key
ws.send(JSON.stringify({ cmd: "push_get_vapid" }));

ws.addEventListener("message", async (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === "push_vapid") {
    const vapidKey = data.key;

    // 2. Convert base64url string to Uint8Array for PushManager
    const appServerKey = urlBase64ToUint8Array(vapidKey);

    // 3. Subscribe to push via the browser
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: appServerKey,
    });

    // 4. Send the subscription to the server
    ws.send(JSON.stringify({
      cmd: "push_subscribe",
      subscription: subscription.toJSON(),
    }));
  }
});

// Utility: convert base64url string → Uint8Array
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}
```

## Related Commands

- [push_subscribe](push_subscribe.md) — Register a push subscription with the server
- [push_unsubscribe](push_unsubscribe.md) — Remove a push subscription

See also: [Web Push Notifications guide](../push_notifications.md)

See implementation: [`handlers/push.py`](../../handlers/push.py) (`handle_push_get_vapid`).
