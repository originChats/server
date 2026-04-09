import json, os, asyncio, base64
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from logger import Logger
from db import push as push_db
from handlers.websocket_utils import _get_ws_attr

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VAPID_DIR = os.path.join(_REPO_ROOT, "vapid")
_PRIVATE_KEY = os.path.join(_VAPID_DIR, "private_key.pem")
_VAPID_CFG = os.path.join(_VAPID_DIR, "vapid_config.json")

_VAPID_PUBLIC_KEY_B64: str = ""
_VAPID_CLAIMS_EMAIL: str = "mailto:"

_push_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="push")


def _derive_public_key_b64(private_key_path: str) -> str:
    from py_vapid import Vapid
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    v = Vapid.from_file(private_key_path)
    if v.public_key is None:
        raise ValueError("Failed to load public key from VAPID key pair")
    raw = v.public_key.public_bytes(encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _save_vapid_config():
    try:
        with open(_VAPID_CFG, "w") as f:
            json.dump({"public_key_b64": _VAPID_PUBLIC_KEY_B64, "claims_email": _VAPID_CLAIMS_EMAIL}, f, indent=4)
    except Exception as exc:
        Logger.warning(f"[Push] Could not save vapid_config.json: {exc}")


def _init_vapid():
    global _VAPID_PUBLIC_KEY_B64, _VAPID_CLAIMS_EMAIL

    os.makedirs(_VAPID_DIR, exist_ok=True)

    if os.path.exists(_VAPID_CFG):
        try:
            with open(_VAPID_CFG) as f:
                cfg = json.load(f)
                _VAPID_PUBLIC_KEY_B64 = cfg.get("public_key_b64", "")
                _VAPID_CLAIMS_EMAIL = cfg.get("claims_email", _VAPID_CLAIMS_EMAIL)
        except Exception as exc:
            Logger.warning(f"[Push] Could not read vapid_config.json: {exc}")

    if not os.path.exists(_PRIVATE_KEY):
        Logger.warning("[Push] VAPID private key not found — generating new key pair.")
        Logger.warning("[Push] Edit vapid/vapid_config.json to set your claims_email before going live.")
        try:
            from py_vapid import Vapid
            v = Vapid()
            v.generate_keys()
            v.save_key(_PRIVATE_KEY)
            _VAPID_PUBLIC_KEY_B64 = _derive_public_key_b64(_PRIVATE_KEY)
            _save_vapid_config()
            Logger.success(f"[Push] VAPID key pair generated. Public key: {_VAPID_PUBLIC_KEY_B64[:20]}...")
        except Exception as exc:
            Logger.error(f"[Push] Failed to generate VAPID keys: {exc}")
            return

    if not _VAPID_PUBLIC_KEY_B64:
        try:
            _VAPID_PUBLIC_KEY_B64 = _derive_public_key_b64(_PRIVATE_KEY)
            _save_vapid_config()
            Logger.info("[Push] Re-derived VAPID public key from existing private key.")
        except Exception as exc:
            Logger.error(f"[Push] Failed to derive VAPID public key: {exc}")


_init_vapid()


def is_user_online(username: str, server_data: dict) -> bool:
    if not server_data:
        return False
    connected_usernames = server_data.get("connected_usernames", {})
    return username in connected_usernames and connected_usernames[username] > 0


def _do_send_push(username: str, title: str, body: str, extra_data: dict):
    if not _VAPID_PUBLIC_KEY_B64 or not os.path.exists(_PRIVATE_KEY):
        Logger.warning("[Push] VAPID keys not available — skipping push notification.")
        return

    subs = push_db.get_subscriptions_for_user(username)
    if not subs:
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        Logger.error("[Push] pywebpush is not installed. Run: pip install pywebpush")
        return

    payload = json.dumps({"title": title, "body": body, **extra_data})

    for sub in subs:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=payload,
                vapid_private_key=_PRIVATE_KEY,
                vapid_claims={"sub": _VAPID_CLAIMS_EMAIL},
                ttl=86400,
            )
            Logger.info(f"[Push] Sent notification to {username} via {sub['endpoint'][:40]}...")
        except WebPushException as exc:
            resp = getattr(exc, "response", None)
            status = resp.status_code if resp is not None else None
            if status in (404, 410):
                Logger.info(f"[Push] Subscription expired (HTTP {status}) — removing.")
                push_db.delete_subscription(sub["endpoint"], username=username)
            else:
                Logger.error(f"[Push] WebPushException for {sub['endpoint'][:40]}: {exc}")
        except Exception as exc:
            Logger.error(f"[Push] Unexpected error for {sub['endpoint'][:40]}: {exc}")


def send_push_notification(username: str, title: str, body: str, extra_data: Optional[dict] = None):
    if extra_data is None:
        extra_data = {}
    body = body[:120]
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_push_executor, _do_send_push, username, title, body, extra_data)


async def handle_push_get_vapid(ws) -> dict:
    if not _VAPID_PUBLIC_KEY_B64:
        return {"cmd": "error", "src": "push_get_vapid", "val": "VAPID keys not configured on this server"}
    return {"cmd": "push_vapid", "key": _VAPID_PUBLIC_KEY_B64}


async def handle_push_subscribe(ws, message: dict) -> dict:
    username = _get_ws_attr(ws, "username")
    if not username:
        return {"cmd": "error", "src": "push_subscribe", "val": "Not authenticated"}

    sub = message.get("subscription")
    if not sub or not isinstance(sub, dict):
        return {"cmd": "error", "src": "push_subscribe", "val": "Missing subscription object"}

    endpoint = sub.get("endpoint")
    keys = sub.get("keys", {})
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        return {"cmd": "error", "src": "push_subscribe", "val": "subscription must include endpoint, keys.p256dh and keys.auth"}

    request = _get_ws_attr(ws, "request")
    device_fingerprint = ""
    if request:
        headers = request.headers
        ip = headers.get("CF-Connecting-IP", "") or headers.get("X-Forwarded-For", "").split(",")[0].strip()
        user_agent = headers.get("User-Agent", "")
        country = headers.get("CF-IPCountry", "")
        device_fingerprint = push_db.compute_device_fingerprint(ip, user_agent, country)

    try:
        push_db.upsert_subscription(username, endpoint, p256dh, auth, device_fingerprint=device_fingerprint)
        Logger.info(f"[Push] Subscription registered for {username} (device: {device_fingerprint[:8]}...)")
        return {"cmd": "push_subscribed", "success": True, "device_fingerprint": device_fingerprint}
    except Exception as exc:
        Logger.error(f"[Push] Failed to save subscription for {username}: {exc}")
        return {"cmd": "error", "src": "push_subscribe", "val": "Failed to save subscription"}


async def handle_push_unsubscribe(ws, message: dict) -> dict:
    username = _get_ws_attr(ws, "username")
    if not username:
        return {"cmd": "error", "src": "push_unsubscribe", "val": "Not authenticated"}

    endpoint = message.get("endpoint")
    if not endpoint:
        return {"cmd": "error", "src": "push_unsubscribe", "val": "Missing endpoint"}

    try:
        push_db.delete_subscription(endpoint, username=username)
        Logger.info(f"[Push] Subscription removed for {username}")
        return {"cmd": "push_unsubscribed", "success": True}
    except Exception as exc:
        Logger.error(f"[Push] Failed to remove subscription for {username}: {exc}")
        return {"cmd": "error", "src": "push_unsubscribe", "val": "Failed to remove subscription"}
