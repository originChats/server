import json
import time
import uuid
from db import channels
from logger import Logger


def format_github_push_message(payload: dict) -> dict:
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
    
    repo = payload.get("repository", {})
    repo_name = repo.get("name", "unknown")
    repo_full_name = repo.get("full_name", "unknown")
    repo_url = repo.get("html_url", "")
    
    sender = payload.get("sender", {})
    sender_name = sender.get("login", "unknown")
    sender_avatar = sender.get("avatar_url", "")
    
    pusher = payload.get("pusher", {})
    pusher_name = pusher.get("name", sender_name)
    
    commits = payload.get("commits", [])
    commit_count = len(commits)
    
    compare_url = payload.get("compare", "")
    
    forced = payload.get("forced", False)
    created = payload.get("created", False)
    deleted = payload.get("deleted", False)
    
    title = ""
    description = ""
    
    if deleted:
        title = f"🗑️ **{branch}** deleted"
        description = f"Branch **{branch}** was deleted in **[{repo_full_name}]({repo_url})** by **{pusher_name}**"
    elif created:
        title = f"🌿 **{branch}** created"
        description = f"New branch **{branch}** created in **[{repo_full_name}]({repo_url})** by **{pusher_name}**"
    elif forced:
        title = f"⚡ **{branch}** force-pushed"
        description = f"**{pusher_name}** force-pushed **{commit_count} commit(s)** to **{branch}** in **[{repo_full_name}]({repo_url})**"
    else:
        title = f"📤 **{branch}** pushed"
        if commit_count == 1:
            description = f"**{commit_count} commit** to **{branch}** in **[{repo_full_name}]({repo_url})**"
        else:
            description = f"**{commit_count} commits** to **{branch}** in **[{repo_full_name}]({repo_url})**"
    
    embed = {
        "title": title,
        "description": description,
        "url": compare_url if compare_url else repo_url,
        "color": 0x24292e,
        "author": {
            "name": pusher_name,
            "icon_url": sender_avatar
        },
        "footer": {
            "text": repo_full_name,
            "icon_url": repo.get("owner", {}).get("avatar_url", "")
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    if commits:
        commit_list = []
        for commit in commits[:5]:
            commit_id = commit.get("id", "")[:7]
            commit_msg = commit.get("message", "").split("\n")[0]
            commit_url = commit.get("url", "")
            commit_author = commit.get("author", {}).get("username", "unknown")
            
            if len(commit_msg) > 50:
                commit_msg = commit_msg[:47] + "..."
            
            commit_list.append(f"[`{commit_id}`]({commit_url}) {commit_msg} - **{commit_author}**")
        
        if len(commits) > 5:
            commit_list.append(f"... and {len(commits) - 5} more commits")
        
        embed["fields"] = [
            {
                "name": "Commits",
                "value": "\n".join(commit_list),
                "inline": False
            }
        ]
    
    return embed


def handle_github_webhook(payload: dict, event_type: str, channel_name: str):
    if event_type == "push":
        embed = format_github_push_message(payload)
        
        message_id = str(uuid.uuid4())
        out_msg = {
            "user": "originChats",
            "content": "",
            "timestamp": time.time(),
            "type": "message",
            "pinned": False,
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
        
        out_msg_for_client = channels.convert_messages_to_user_format([out_msg])[0]
        out_msg_for_client["embeds"] = [embed]
        out_msg_for_client["webhook"] = out_msg["webhook"]
        
        return out_msg_for_client, None
    
    Logger.info(f"[GitHub Webhook] Received unhandled event type: {event_type}")
    return None, f"Unhandled event type: {event_type}"
