import json
import os
from . import users
import emoji

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

channels_db_dir = os.path.join(_MODULE_DIR, "channels")
channels_index = os.path.join(_MODULE_DIR, "channels.json")


def get_channel(channel_name):
    data = get_channels()
    for channel in data:
        if channel.get("name") == channel_name:
            return channel
    return None


def get_channel_messages(channel_name, start, limit):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        return []

    if not limit:
        limit = 100

    if limit > 200:
        limit = 200
    
    if isinstance(start, int):
        if start < 0:
            start = 0
        end = len(channel_data) - start
        begin = max(0, end - limit)
    else:
        index = None
        for i, msg in enumerate(channel_data):
            if msg.get('id') == start:
                index = i
                break
        if index is None:
            return []
        end = index
        begin = max(0, end - limit)

    channel_data_len = len(channel_data)
    if begin > channel_data_len:
        return []
    if end > channel_data_len:
        end = channel_data_len
    
    if begin < 0:
        begin = 0
    if end < 0:
        end = 0

    if begin == end:
        return []
    
    return channel_data[begin:end]


def convert_messages_to_user_format(messages):
    converted = []
    for msg in messages:
        msg_copy = msg.copy()
        if "user" in msg_copy:
            user_id = msg_copy["user"]
            username = users.get_username_by_id(user_id)
            msg_copy["user"] = username if username else user_id
        if "reply_to" in msg_copy and "user" in msg_copy["reply_to"]:
            user_id = msg_copy["reply_to"]["user"]
            username = users.get_username_by_id(user_id)
            msg_copy["reply_to"]["user"] = username if username else user_id
        if "reactions" in msg_copy:
            converted_reactions = {}
            for emoji_key, user_ids in msg_copy["reactions"].items():
                usernames = []
                for uid in user_ids:
                    username = users.get_username_by_id(uid)
                    usernames.append(username if username else uid)
                converted_reactions[emoji_key] = usernames
            msg_copy["reactions"] = converted_reactions
        converted.append(msg_copy)
    return converted


def save_channel_message(channel_name, message):
    os.makedirs(channels_db_dir, exist_ok=True)
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        channel_data = []

    channel_data.append(message)

    with open(f"{channels_db_dir}/{channel_name}.json", 'w', encoding='utf-8') as f:
        json.dump(channel_data, f, separators=(',', ':'), ensure_ascii=False)

    return True


def get_all_channels_for_roles(roles):
    channels_list = []
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            all_channels = json.load(f)
        for channel in all_channels:
            permissions = channel.get("permissions", {})
            view_roles = permissions.get("view", [])
            if any(role in view_roles for role in roles):
                channels_list.append(channel)
    except FileNotFoundError:
        return []
    return channels_list


def edit_channel_message(channel_name, message_id, new_content):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                msg["content"] = new_content
                msg["edited"] = True
                break
        else:
            return False

        os.makedirs(channels_db_dir, exist_ok=True)
        with open(f"{channels_db_dir}/{channel_name}.json", 'w', encoding='utf-8') as f:
            json.dump(channel_data, f, separators=(',', ':'), ensure_ascii=False)

        return True
    except FileNotFoundError:
        return False


def get_channel_message(channel_name, message_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        i = 0
        for msg in channel_data:
            i += 1
            if msg.get("id") == message_id:
                msg["position"] = i
                return msg
        return None
    except FileNotFoundError:
        return None


def does_user_have_permission(channel_name, user_roles, permission_type):
    if "owner" in user_roles:
        return True
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)

        for channel in channels_data:
            if channel.get('name') == channel_name:
                permissions = channel.get('permissions', {})
                allowed_roles = permissions.get(permission_type, [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False

    return False


def delete_channel_message(channel_name, message_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        new_data = [msg for msg in channel_data if msg.get("id") != message_id]

        os.makedirs(channels_db_dir, exist_ok=True)
        with open(f"{channels_db_dir}/{channel_name}.json", 'w', encoding='utf-8') as f:
            json.dump(new_data, f, separators=(',', ':'), ensure_ascii=False)

        return True
    except FileNotFoundError:
        return False


def get_channels():
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def create_channel(channel_name, channel_type):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels = json.load(f)
    except FileNotFoundError:
        channels = []

    if any(channel.get('name') == channel_name for channel in channels):
        return False

    new_channel = {
        "name": channel_name,
        "type": channel_type,
        "permissions": {
            "view": ["owner"],
            "send": ["owner"]
        }
    }

    channels.append(new_channel)

    with open(channels_index, 'w', encoding='utf-8') as f:
        json.dump(channels, f, indent=4)

    return True


def can_user_pin(channel_name, user_roles):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "pin" not in permissions:
                    return True
                allowed_roles = permissions.get("pin", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False

    return False


def pin_channel_message(channel_name, message_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        return False

    for msg in channel_data:
        if msg.get("id") == message_id:
            msg["pinned"] = True
            break
    else:
        return False

    with open(f"{channels_db_dir}/{channel_name}.json", 'w', encoding='utf-8') as f:
        json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

    return True


def unpin_channel_message(channel_name, message_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        return False

    for msg in channel_data:
        if msg.get("id") == message_id:
            msg["pinned"] = False
            break
    else:
        return False

    with open(f"{channels_db_dir}/{channel_name}.json", 'w', encoding='utf-8') as f:
        json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

    return True


def get_pinned_messages(channel_name):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            messages = json.load(f)
    except FileNotFoundError:
        return []

    pinned = [msg for msg in messages if msg.get("pinned")]
    return list(reversed(pinned))


def search_channel_messages(channel_name, query):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            messages = json.load(f)
    except FileNotFoundError:
        return []

    search_results = [msg for msg in messages if query in msg.get("content", "").lower()]
    return list(reversed(search_results))


def delete_channel(channel_name):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        new_channels = [channel for channel in channels if channel.get('name') != channel_name]

        if len(new_channels) == len(channels):
            return False

        with open(channels_index, 'w', encoding='utf-8') as f:
            json.dump(new_channels, f, indent=4)

        os.remove(f"{channels_db_dir}/{channel_name}.json")

        return True
    except FileNotFoundError:
        return False


def set_channel_permissions(channel_name, role, permission, allow=True):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        for channel in channels:
            if channel.get('name') == channel_name:
                if permission not in channel['permissions']:
                    channel['permissions'][permission] = []
                if role not in channel['permissions'][permission]:
                    if allow:
                        channel['permissions'][permission].append(role)
                    else:
                        if role in channel['permissions'][permission]:
                            channel['permissions'][permission].remove(role)
                with open(channels_index, 'w', encoding='utf-8') as f:
                    json.dump(channels, f, indent=4)
                return True
        return False
    except FileNotFoundError:
        return False


def get_channel_permissions(channel_name):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        for channel in channels:
            if channel.get('name') == channel_name:
                return channel.get('permissions', {})
        return None
    except FileNotFoundError:
        return None


def reorder_channel(channel_name, new_position):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        for i, channel in enumerate(channels):
            if channel.get('name') == channel_name:
                channels.pop(i)
                channels.insert(int(new_position), channel)
                with open(channels_index, 'w', encoding='utf-8') as f:
                    json.dump(channels, f, indent=4)
                return True
        return False
    except FileNotFoundError:
        return False


def get_message_replies(channel_name, message_id, limit=50):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        replies = []
        for msg in channel_data:
            if msg.get("reply_to", {}).get("id") == message_id:
                replies.append(msg)
                if len(replies) >= limit:
                    break
        return replies
    except FileNotFoundError:
        return []


def purge_messages(channel_name, count):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        if len(channel_data) < count:
            return False

        new_data = channel_data[:-count]

        with open(f"{channels_db_dir}/{channel_name}.json", 'w', encoding='utf-8') as f:
            json.dump(new_data, f, separators=(',', ':'), ensure_ascii=False)

        return True
    except FileNotFoundError:
        return False


def can_user_delete_own(channel_name, user_roles):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "delete_own" not in permissions:
                    return True
                allowed_roles = permissions.get("delete_own", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return True
    return True


def can_user_edit_own(channel_name, user_roles):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "edit_own" not in permissions:
                    return True
                allowed_roles = permissions.get("edit_own", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False
    return False


def can_user_react(channel_name, user_roles):
    try:
        with open(channels_index, 'r', encoding='utf-8') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "react" not in permissions:
                    return True
                allowed_roles = permissions.get("react", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False
    return False


def add_reaction(channel_name, message_id, emoji_str, user_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                if emoji_str not in emoji.EMOJI_DATA:
                    return False

                msg.setdefault("reactions", {})
                msg["reactions"].setdefault(emoji_str, [])

                if user_id in msg["reactions"][emoji_str]:
                    return True

                msg["reactions"][emoji_str].append(user_id)

                with open(f"{channels_db_dir}/{channel_name}.json", "w", encoding='utf-8') as f:
                    json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

                return True

        return False

    except FileNotFoundError:
        return False


def remove_reaction(channel_name, message_id, emoji_str, user_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                if emoji_str not in emoji.EMOJI_DATA:
                    return False

                reactions = msg.get("reactions", {})
                if emoji_str not in reactions:
                    return False

                if user_id not in reactions[emoji_str]:
                    return False

                reactions[emoji_str].remove(user_id)

                if not reactions[emoji_str]:
                    del reactions[emoji_str]
                if not reactions:
                    del msg["reactions"]

                with open(f"{channels_db_dir}/{channel_name}.json", "w", encoding='utf-8') as f:
                    json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

                return True

        return False

    except FileNotFoundError:
        return False
   

def get_reactions(channel_name, message_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                return msg.get("reactions", {})
        return None
    except FileNotFoundError:
        return None
    

def get_reaction_users(channel_name, message_id, emoji):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                if emoji in msg.get("reactions", {}):
                    return msg["reactions"][emoji]
        return None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
