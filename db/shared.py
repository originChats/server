from . import users
from typing import List


def convert_messages_to_user_format(messages: List[dict]) -> List[dict]:
    """Convert messages with user IDs to messages with usernames for sending to clients."""
    user_ids_needed = set()
    for msg in messages:
        if "user" in msg:
            user_ids_needed.add(msg["user"])
        if "reply_to" in msg and "user" in msg["reply_to"]:
            user_ids_needed.add(msg["reply_to"]["user"])
        if "reactions" in msg:
            for uid_list in msg["reactions"].values():
                user_ids_needed.update(uid_list)

    uid_to_name = {uid: users.get_username_by_id(uid) for uid in user_ids_needed}

    converted = []
    for msg in messages:
        msg_copy = msg.copy()

        if "user" in msg_copy:
            uid = msg_copy["user"]
            msg_copy["user"] = uid_to_name.get(uid) or uid

        if "reply_to" in msg_copy and "user" in msg_copy["reply_to"]:
            msg_copy["reply_to"] = msg_copy["reply_to"].copy()
            uid = msg_copy["reply_to"]["user"]
            msg_copy["reply_to"]["user"] = uid_to_name.get(uid) or uid

        if "reactions" in msg_copy:
            converted_reactions = {}
            for emo, uid_list in msg_copy["reactions"].items():
                converted_reactions[emo] = [uid_to_name.get(u) or u for u in uid_list]
            msg_copy["reactions"] = converted_reactions

        msg_copy.setdefault("pinned", False)
        msg_copy.setdefault("type", "message")
        msg_copy.setdefault("interaction", msg.get("interaction"))

        converted.append(msg_copy)

    return converted
