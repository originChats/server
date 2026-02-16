import json, os
from . import users
import emoji

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

channels_db_dir = os.path.join(_MODULE_DIR, "channels")
channels_index = os.path.join(_MODULE_DIR, "channels.json")

def get_channel(channel_name):
    """
    Get channel data by channel name.
    """
    data = get_channels()
    for channel in data:
        if channel.get("name") == channel_name:
            return channel
    return None

def get_channel_messages(channel_name, start, limit):
    """
    Retrieve messages from a specific channel.

    Args:
        channel_name (str): The name of the channel to retrieve messages from.
        start (int or str, optional): If int, the number of recent messages to skip (offset from the end). 
                                      If str, the message ID to retrieve messages before (older messages than the specified ID). 
                                      Defaults to 0.
        limit (int, optional): The maximum number of messages to retrieve. Defaults to 100.

    Returns:
        list: A list of messages from the specified channel, in chronological order (oldest first).
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
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
    """
    Convert messages with user IDs to messages with usernames for sending to clients.
    This ensures clients never see user IDs, only usernames.
    """
    converted = []
    for msg in messages:
        msg_copy = msg.copy()
        
        # Convert user ID to username
        if "user" in msg_copy:
            user_id = msg_copy["user"]
            username = users.get_username_by_id(user_id)
            msg_copy["user"] = username if username else user_id  # Fallback to ID if username not found
        
        # Convert reply_to user ID to username if present
        if "reply_to" in msg_copy and "user" in msg_copy["reply_to"]:
            user_id = msg_copy["reply_to"]["user"]
            username = users.get_username_by_id(user_id)
            msg_copy["reply_to"]["user"] = username if username else user_id  # Fallback to ID if username not found
        
        # Convert user IDs in reactions to usernames if present
        if "reactions" in msg_copy:
            converted_reactions = {}
            for emoji, user_ids in msg_copy["reactions"].items():
                usernames = []
                for uid in user_ids:
                    username = users.get_username_by_id(uid)
                    usernames.append(username if username else uid)  # Fallback to ID if username not found
                converted_reactions[emoji] = usernames
            msg_copy["reactions"] = converted_reactions
        
        converted.append(msg_copy)
    
    return converted

def save_channel_message(channel_name, message):
    """
    Save a message to a specific channel.

    Args:
        channel_name (str): The name of the channel to save the message to.
        message (dict): The message to save, should contain 'user', 'content', and 'timestamp'.

    Returns:
        bool: True if the message was saved successfully, False otherwise.
    """
    # Ensure the channels directory exists
    os.makedirs(channels_db_dir, exist_ok=True)
    
    # Load existing channel data or create a new one
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        channel_data = []

    # Append the new message
    channel_data.append(message)

    # Save the updated channel data with compact formatting
    with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
        json.dump(channel_data, f, separators=(',', ':'), ensure_ascii=False)

    return True

def get_all_channels_for_roles(roles):
    """
    Get all channels available for the specified roles.

    Args:
        roles (list): A list of roles to filter channels by.

    Returns:
        list: A list of channel info dicts available for the specified roles.
    """
    channels = []
    try:
        with open(channels_index, 'r') as f:
            all_channels = json.load(f)
        for channel in all_channels:
            permissions = channel.get("permissions", {})
            view_roles = permissions.get("view", [])
            if any(role in view_roles for role in roles):
                channels.append(channel)
    except FileNotFoundError:
        return []
    return channels

def edit_channel_message(channel_name, message_id, new_content):
    """
    Edit a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to edit.
        new_content (str): The new content for the message.

    Returns:
        bool: True if the message was edited successfully, False otherwise.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                msg["content"] = new_content
                msg["edited"] = True
                break
        else:
            return False  # Message not found

        # Ensure the channels directory exists
        os.makedirs(channels_db_dir, exist_ok=True)
        
        with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
            json.dump(channel_data, f, separators=(',', ':'), ensure_ascii=False)

        return True
    except FileNotFoundError:
        return False

def get_channel_message(channel_name, message_id):
    """
    Retrieve a specific message from a channel by its ID.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to retrieve.

    Returns:
        dict: The message if found, None otherwise.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)

        i = 0
        for msg in channel_data:
            i += 1
            if msg.get("id") == message_id:
                msg["position"] = i
                return msg
        return None  # Message not found
    except FileNotFoundError:
        return None  # Channel not found
    
def does_user_have_permission(channel_name, user_roles, permission_type):
    """
    Check if a user with specific roles has permission to perform an action on a channel.

    Args:
        channel_name (str): The name of the channel.
        user_roles (list): A list of roles assigned to the user.
        permission_type (str): The type of permission to check (e.g., "view", "edit_own").

    Returns:
        bool: True if the user has the required permission, False otherwise.
    """
    if "owner" in user_roles:
        return True
    try:
        with open(channels_index, 'r') as f:
            channels_data = json.load(f)

        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                allowed_roles = permissions.get(permission_type, [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False  # Channel index not found

    return False  # Channel not found
    
def delete_channel_message(channel_name, message_id):
    """
    Delete a message from a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to delete.

    Returns:
        bool: True if the message was deleted successfully, False otherwise.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)

        new_data = [msg for msg in channel_data if msg.get("id") != message_id]

        # Ensure the channels directory exists
        os.makedirs(channels_db_dir, exist_ok=True)
        
        with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
            json.dump(new_data, f, separators=(',', ':'), ensure_ascii=False)

        return True
    except FileNotFoundError:
        return False
    
def get_channels():
    """
    Get all channels from the channels index.

    Returns:
        list: A list of channel info dicts.
    """
    try:
        with open(channels_index, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []  # No channels found
    
def create_channel(channel_name, channel_type, description=None, wallpaper=None, permissions=None, size=None):
    """
    Create a new channel.

    Args:
        channel_name (str): The name of the channel to create.
        channel_type (str): The type of the channel (e.g., "text", "voice", "separator").
        description (str, optional): Channel description.
        wallpaper (str, optional): Wallpaper URL.
        permissions (dict, optional): Channel permissions.
        size (int, optional): Size for separator channels.

    Returns:
        bool: True if the channel was created successfully, False if it already exists.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)
    except FileNotFoundError:
        channels = []

    # Check if the channel already exists
    if any(channel.get('name') == channel_name for channel in channels):
        return False  # Channel already exists

    new_channel = {
        "name": channel_name,
        "type": channel_type
    }

    if channel_type != "separator":
        new_channel["permissions"] = permissions or {
            "view": ["owner"],
            "send": ["owner"]
        }
    
    if description:
        new_channel["description"] = description
    
    if wallpaper:
        new_channel["wallpaper"] = wallpaper
    
    if size and channel_type == "separator":
        new_channel["size"] = size

    channels.append(new_channel)

    # Save the updated channels index
    with open(channels_index, 'w') as f:
        json.dump(channels, f, indent=4)

    # For text and voice channels, create an empty messages file
    if channel_type in ["text", "voice"]:
        os.makedirs(channels_db_dir, exist_ok=True)
        with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
            json.dump([], f, separators=(',', ':'), ensure_ascii=False)

    return True

def can_user_pin(channel_name, user_roles):
    """
    Check if a user with specific roles can pin messages in a channel.
    If the channel does not specify pin, only owner is allowed by default
    """
    try:
        with open(channels_index, 'r') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "pin" not in permissions:
                    return True  # Default: owner can pin
                allowed_roles = permissions.get("pin", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False
    
def pin_channel_message(channel_name, message_id):
    """
    Pin a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to pin.

    Returns:
        bool: True if the message was pinned successfully, False otherwise.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        return False

    for msg in channel_data:
        if msg.get("id") == message_id:
            msg["pinned"] = True
            break
    else:
        return False  # Message not found

    # Save the updated channel data
    with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
        json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

    return True

def unpin_channel_message(channel_name, message_id):
    """
    Unpin a message in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to unpin.

    Returns:
        bool: True if the message was unpinned successfully, False otherwise.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)
    except FileNotFoundError:
        return False

    for msg in channel_data:
        if msg.get("id") == message_id:
            msg["pinned"] = False
            break
    else:
        return False  # Message not found

    # Save the updated channel data
    with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
        json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

    return True

def get_pinned_messages(channel_name):
    """
    Get the pinned messages in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        limit (int): The maximum number of messages to retrieve.

    Returns:
        list: A list of all pinned messages in a channel
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            messages = json.load(f)
    except FileNotFoundError:
        return []

    pinned = [msg for msg in messages if msg.get("pinned")]
    return list(reversed(pinned))

def search_channel_messages(channel_name, query):
    """
    Search for messages in a specific channel.

    Args:
        channel_name (str): The name of the channel.
        query (str): The search query.
        limit (int): The maximum number of messages to retrieve.

    Returns:
        list: A list of messages that match the search query.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            messages = json.load(f)
    except FileNotFoundError:
        return []

    search_results = [msg for msg in messages if query in msg.get("content", "").lower()]
    return list(reversed(search_results))

def delete_channel(channel_name):
    """
    Delete a channel.

    Args:
        channel_name (str): The name of the channel to delete.

    Returns:
        bool: True if the channel was deleted successfully, False if it does not exist.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)

        new_channels = [channel for channel in channels if channel.get('name') != channel_name]

        if len(new_channels) == len(channels):
            return False  # Channel not found

        # Save the updated channels index
        with open(channels_index, 'w') as f:
            json.dump(new_channels, f, indent=4)

        # Remove the channel's message file
        os.remove(f"{channels_db_dir}/{channel_name}.json")

        return True
    except FileNotFoundError:
        return False  # Channels index not found
    
def set_channel_permissions(channel_name, role, permission, allow=True):
    """
    Set permissions for a specific role on a channel.

    Args:
        channel_name (str): The name of the channel.
        role (str): The role to set permissions for.
        permission (str): The permission to set (e.g., "view", "edit_own", "send").

    Returns:
        bool: True if permissions were set successfully, False if the channel does not exist.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)

        for channel in channels:
            if channel.get('name') == channel_name:
                if permission not in channel['permissions']:
                    channel['permissions'][permission] = []
                if role not in channel['permissions'][permission]:
                    if allow:
                        channel['permissions'][permission].append(role)
                    else:                        # If removing permission, ensure the role exists before removing
                        if role in channel['permissions'][permission]:
                            channel['permissions'][permission].remove(role)
                
                # Save the updated channels index
                with open(channels_index, 'w') as f:
                    json.dump(channels, f, indent=4)
                
                return True
        
        return False  # Channel not found
    except FileNotFoundError:
        return False  # Channels index not found
    
def get_channel_permissions(channel_name):
    """
    Get permissions for a specific channel.

    Args:
        channel_name (str): The name of the channel.

    Returns:
        dict: A dictionary of permissions for the channel, or None if the channel does not exist.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)

        for channel in channels:
            if channel.get('name') == channel_name:
                return channel.get('permissions', {})
        
        return None  # Channel not found
    except FileNotFoundError:
        return None  # Channels index not found
    
def reorder_channel(channel_name, new_position):
    """
    Reorder a channel in the channels index.

    Args:
        channel_name (str): The name of the channel to reorder.
        new_position (int): The new position for the channel (0-based index).

    Returns:
        bool: True if the channel was reordered successfully, False if it does not exist.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)

        for i, channel in enumerate(channels):
            if channel.get('name') == channel_name:
                # Remove the channel from its current position
                channels.pop(i)
                # Insert it at the new position
                channels.insert(int(new_position), channel)

                # Save the updated channels index
                with open(channels_index, 'w') as f:
                    json.dump(channels, f, indent=4)
                
                return True
        
        return False  # Channel not found
    except FileNotFoundError:
        return False  # Channels index not found

def get_message_replies(channel_name, message_id, limit=50):
    """
    Get all replies to a specific message.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to get replies for.
        limit (int): Maximum number of replies to return.

    Returns:
        list: A list of messages that are replies to the specified message.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)

        replies = []
        for msg in channel_data:
            if msg.get("reply_to", {}).get("id") == message_id:
                replies.append(msg)
                if len(replies) >= limit:
                    break
        
        return replies
    except FileNotFoundError:
        return []  # Channel not found
    
def purge_messages(channel_name, count):
    """
    Purge the last 'count' messages from a channel.

    Args:
        channel_name (str): The name of the channel.
        count (int): The number of messages to purge.

    Returns:
        bool: True if messages were purged successfully, False if the channel does not exist or has fewer messages.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)

        if len(channel_data) < count:
            return False  # Not enough messages to purge

        # Remove the last 'count' messages
        new_data = channel_data[:-count]

        # Save the updated channel data
        with open(f"{channels_db_dir}/{channel_name}.json", 'w') as f:
            json.dump(new_data, f, separators=(',', ':'), ensure_ascii=False)

        return True
    except FileNotFoundError:
        return False  # Channel not found

def can_user_delete_own(channel_name, user_roles):
    """
    Check if a user with specific roles can delete their own message in a channel.
    If the channel does not specify delete_own, all roles are allowed by default.
    """
    try:
        with open(channels_index, 'r') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "delete_own" not in permissions:
                    return True  # Default: all roles can delete their own messages
                allowed_roles = permissions.get("delete_own", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return True  # Default to True if channel index not found
    return True  # Default to True if channel not found

def can_user_edit_own(channel_name, user_roles):
    """
    Check if a user with specific roles can edit their own message in a channel.
    If the channel does not specify edit_own, all roles are allowed by default.
    """
    try:
        with open(channels_index, 'r') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "edit_own" not in permissions:
                    return True  # Default: all roles can edit their own messages
                allowed_roles = permissions.get("edit_own", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False
    return False

def can_user_react(channel_name, user_roles):
    """
    Check if a user with specific roles can react to messages in a channel.
    If the channel does not specify react, all roles are allowed by default.
    """
    try:
        with open(channels_index, 'r') as f:
            channels_data = json.load(f)
        for channel in channels_data:
            if channel.get("name") == channel_name:
                permissions = channel.get("permissions", {})
                if "react" not in permissions:
                    return True  # Default: all roles can react
                allowed_roles = permissions.get("react", [])
                return any(role in allowed_roles for role in user_roles)
    except FileNotFoundError:
        return False
    return False

def add_reaction(channel_name, message_id, emoji_str, user_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json") as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                if emoji_str not in emoji.EMOJI_DATA:
                    return False

                msg.setdefault("reactions", {})
                msg["reactions"].setdefault(emoji_str, [])

                if user_id in msg["reactions"][emoji_str]:
                    return True  # already reacted

                msg["reactions"][emoji_str].append(user_id)

                with open(f"{channels_db_dir}/{channel_name}.json", "w") as f:
                    json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

                return True

        return False

    except FileNotFoundError:
        return False

def remove_reaction(channel_name, message_id, emoji_str, user_id):
    try:
        with open(f"{channels_db_dir}/{channel_name}.json") as f:
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

                with open(f"{channels_db_dir}/{channel_name}.json", "w") as f:
                    json.dump(channel_data, f, separators=(",", ":"), ensure_ascii=False)

                return True

        return False

    except FileNotFoundError:
        return False
   
def get_reactions(channel_name, message_id):
    """
    Get the reactions for a specific message in a channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to get the reactions for.

    Returns:
        dict: A dictionary containing the reactions for the message, or None if the message or channel does not exist.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
            channel_data = json.load(f)

        for msg in channel_data:
            if msg.get("id") == message_id:
                return msg.get("reactions", {})
        
        return None
    except FileNotFoundError:
        return None
    
def get_reaction_users(channel_name, message_id, emoji):
    """
    Get the users who reacted with a specific emoji to a specific message in a channel.

    Args:
        channel_name (str): The name of the channel.
        message_id (str): The ID of the message to get the reactions for.
        emoji (str): The emoji to get the users for.

    Returns:
        list: A list of usernames who reacted with the specified emoji, or None if the message or channel does not exist.
    """
    try:
        with open(f"{channels_db_dir}/{channel_name}.json", 'r') as f:
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

def channel_exists(channel_name):
    """
    Check if a channel exists in the channels index.

    Args:
        channel_name (str): The name of the channel to check.

    Returns:
        bool: True if the channel exists, False otherwise.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)
        return any(channel.get('name') == channel_name for channel in channels)
    except FileNotFoundError:
        return False

def update_channel(channel_name, updates):
    """
    Update a channel's properties. Can rename the channel if 'name' is in updates.

    Args:
        channel_name (str): The current name of the channel to update.
        updates (dict): The updates to apply. Can include:
            - name (str): New channel name (optional)
            - type (str): Channel type (optional)
            - description (str): Channel description (optional)
            - permissions (dict): Channel permissions (optional)
            - wallpaper (str): Wallpaper URL (optional)
            - size (int): Separator size (optional, for separator type)

    Returns:
        bool: True if the channel was updated successfully, False if it does not exist.
    """
    try:
        with open(channels_index, 'r') as f:
            channels = json.load(f)
    except FileNotFoundError:
        return False

    for channel in channels:
        if channel.get('name') == channel_name:
            old_name = channel_name
            
            for key, value in updates.items():
                if key in ['name', 'type', 'description', 'permissions', 'wallpaper', 'size']:
                    channel[key] = value
            
            new_name = channel.get('name', old_name)
            
            if new_name != old_name and channel.get('type') != 'separator':
                old_file_path = f"{channels_db_dir}/{old_name}.json"
                new_file_path = f"{channels_db_dir}/{new_name}.json"
                if os.path.exists(old_file_path):
                    os.rename(old_file_path, new_file_path)
            
            with open(channels_index, 'w') as f:
                json.dump(channels, f, indent=4)
            
            return True
    
    return False