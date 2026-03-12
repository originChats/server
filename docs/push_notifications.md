# Web Push Notifications

OriginChats supports Web Push (RFC 8030), allowing the server to deliver notifications to a user's browser even when the chat tab is closed — as long as the browser itself is running.

---

## How It Works

1. The client requests the server's VAPID public key ([`push_get_vapid`](commands/push_get_vapid.md)).
2. The client calls `PushManager.subscribe()` using that key and sends the resulting subscription object to the server ([`push_subscribe`](commands/push_subscribe.md)).
3. When a user is **offline** (no active WebSocket connection) and a relevant event occurs — a `@mention` or a reply to one of their messages — the server sends an HTTP POST to the subscription's `endpoint` URL.
4. The browser vendor (Google, Mozilla, etc.) delivers the payload to the device. The client's service worker wakes up and displays a notification.

```
Client                   Server                Push Service         Browser
  │──── push_get_vapid ───▶│                         │                  │
  │◀─── push_vapid ────────│                         │                  │
  │                        │                         │                  │
  │──── push_subscribe ───▶│                         │                  │
  │◀─── push_subscribed ───│                         │                  │
  │                        │                         │                  │
  │  (user goes offline)   │                         │                  │
  │                        │                         │                  │
  │                        │──── HTTP POST ─────────▶│                  │
  │                        │                         │──── deliver ────▶│
  │                        │                         │                  │
  │                   service worker wakes, showNotification()          │
```

---

## Server Setup

### 1. Install the dependency

```bash
pip install pywebpush
```

This is already included in `requirements.txt`.

### 2. VAPID keys

VAPID (Voluntary Application Server Identification) keys are used to authenticate the server with push services. They are generated **automatically on first startup** if not already present.

Key files are stored in the `vapid/` directory at the project root:

| File | Purpose |
|------|---------|
| `vapid/private_key.pem` | EC private key — **never commit or share this** |
| `vapid/vapid_config.json` | Stores the base64url public key and claims email |

Both files are excluded from version control via `.gitignore`.

### 3. Set your claims email

Before going to production, edit `vapid/vapid_config.json` and update the `claims_email` field to a real contact address for your server:

```json
{
  "public_key_b64": "BH56TzQe...",
  "claims_email": "mailto:admin@yourserver.com"
}
```

This email is sent to push services as part of VAPID authentication. It is not exposed to users.

> **Important:** VAPID keys should never be rotated once clients have subscribed. Rotating keys invalidates all existing subscriptions and requires every client to re-subscribe.

---

## Push Subscription Storage

Subscriptions are persisted in `db/push_subscriptions.json`. The file is created automatically on first startup.

Schema (keyed by endpoint URL):

```json
{
  "https://fcm.googleapis.com/fcm/send/abc...": {
    "username":   "alice",
    "p256dh":     "BNcRdreALRFXTkOOUHK...",
    "auth":       "tBHItJI5svbpez7KI4...",
    "created_at": 1700000000.0
  }
}
```

A user may have multiple subscriptions (one per browser/device). All of them receive the notification simultaneously.

---

## When Notifications Are Sent

The server sends a push notification when **all** of the following are true:

1. A `message_new` event occurs.
2. The target user has **no active WebSocket connection** (they are offline).
3. The target user has at least one stored push subscription.

### Events that trigger a push

| Event | Trigger condition |
|-------|------------------|
| `@mention` | Message content contains `@username` matching an offline user |
| Reply notification | Message has a `reply_to` referencing a message by an offline user, and `ping` is not `false` |

Role mentions (`@&rolename`) do **not** trigger push notifications.

### Ping suppression

The `ping: false` flag on a [`message_new`](commands/message_new.md) request suppresses both the `pings_get` entry and the push notification for the replied-to user. See [message_new](commands/message_new.md) for details.

---

## Notification Payload

The server sends a JSON payload to the push service. The service worker on the client receives this and calls `showNotification()`.

```json
{
  "title": "#general — alice",
  "body": "hey @bob did you see this?",
  "channelName": "general"
}
```

| Field | Content |
|-------|---------|
| `title` | `#<channel> — <sender>` for mentions; `#<channel> — <sender> replied` for replies |
| `body` | Message content, truncated to 120 characters |
| `channelName` | Name of the channel where the message was sent |

Payloads are limited to **4 KB** by the Web Push specification. The server truncates `body` to 120 characters to stay well within this limit.

Notifications have a **TTL of 86400 seconds (24 hours)**. If the device is offline when the notification is sent, the push service will retry delivery for up to 24 hours before dropping it.

---

## Expired Subscription Cleanup

When a push service returns HTTP `404` or `410` for a subscription endpoint, the subscription is automatically deleted from `db/push_subscriptions.json`. This keeps storage clean and avoids wasted network requests.

---

## Commands Reference

| Command | Direction | Description |
|---------|-----------|-------------|
| [`push_get_vapid`](commands/push_get_vapid.md) | client → server | Request the server's VAPID public key |
| [`push_subscribe`](commands/push_subscribe.md) | client → server | Register a push subscription |
| [`push_unsubscribe`](commands/push_unsubscribe.md) | client → server | Remove a push subscription |

---

## Client Integration

### Full subscription flow

```javascript
async function enablePushNotifications(ws) {
  // 1. Check browser support
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    console.warn("Web Push not supported in this browser.");
    return;
  }

  // 2. Request notification permission
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    console.warn("Notification permission denied.");
    return;
  }

  // 3. Fetch VAPID public key from server
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

### Disabling push notifications

```javascript
async function disablePushNotifications(ws) {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;

  // Unsubscribe in the browser first
  await subscription.unsubscribe();

  // Then tell the server to remove the stored subscription
  ws.send(JSON.stringify({
    cmd: "push_unsubscribe",
    endpoint: subscription.endpoint,
  }));
}
```

### Minimal service worker push handler

The service worker must listen for `push` events to show notifications. The payload shape sent by the server matches what is expected below:

```javascript
// sw.js
self.addEventListener("push", (event) => {
  if (!event.data) return;

  const payload = event.data.json();

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      data: {
        channelName: payload.channelName,
      },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow("/"));
});
```

---

## Implementation Files

| File | Purpose |
|------|---------|
| `handlers/push.py` | VAPID key management, command handlers, `send_push_notification()` |
| `db/push.py` | Flat-file subscription store helpers |
| `db/push_subscriptions.json` | Persisted subscriptions (auto-created) |
| `vapid/private_key.pem` | VAPID private key (auto-generated, gitignored) |
| `vapid/vapid_config.json` | Public key and claims email (auto-generated, gitignored) |
