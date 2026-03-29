import json
import time
import uuid
from db import channels
from db import shared
from logger import Logger


def format_github_push_message(payload: dict) -> dict:
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref

    repo = payload.get("repository", {})
    repo_full_name = repo.get("full_name", "unknown")
    repo_url = repo.get("html_url", "")

    sender = payload.get("sender", {})
    pusher_name = sender.get("login", "unknown")

    commits = payload.get("commits", [])
    commit_count = len(commits)

    compare_url = payload.get("compare", "")

    forced = payload.get("forced", False)
    created = payload.get("created", False)
    deleted = payload.get("deleted", False)

    if deleted:
        title = f"{branch} deleted"
    elif created:
        title = f"{branch} created"
    elif forced:
        title = f"{branch} force-pushed"
    else:
        title = f"{branch}: {commit_count} commit{'s' if commit_count != 1 else ''}"

    embed = {
        "title": title,
        "url": compare_url if compare_url else repo_url,
        "color": 0x24292e,
        "author": {
            "name": f"{pusher_name} - {repo_full_name}",
            "url": repo_url,
            "icon_url": sender.get("avatar_url", "")
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    if commits:
        commit_list = []
        for commit in commits:
            commit_id = commit.get("id", "")[:7]
            commit_msg = commit.get("message", "").split("\n")[0]
            commit_url = commit.get("url", "")
            commit_list.append(f"[`{commit_id}`]({commit_url}) {commit_msg}")

        embed["description"] = "\n".join(commit_list)

    return embed


async def handle_github_webhook(payload: dict, event_type: str, channel_name: str):
    if event_type == "push":
        embed = format_github_push_message(payload)

        message_id = str(uuid.uuid4())
        out_msg = {
            "user": "originChats",
            "content": "",
            "timestamp": time.time(),
            "id": message_id,
            "webhook": {
                "id": "github",
                "name": "GitHub",
                "avatar": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
            },
            "embeds": [embed]
        }

        if not channels.channel_exists(channel_name):
            return None, "Channel not found"

        channels.save_channel_message(channel_name, out_msg)

        out_msg_for_client = shared.convert_messages_to_user_format([out_msg])
        out_msg_for_client = out_msg_for_client[0]
        out_msg_for_client["embeds"] = [embed]
        out_msg_for_client["webhook"] = out_msg["webhook"]

        return out_msg_for_client, None

    Logger.info(f"[GitHub Webhook] Received unhandled event type: {event_type}")
    return None, f"Unhandled event type: {event_type}"
