import re
from db import users, roles


def extract_user_mentions(content, exclude_username=None):
    mentioned = set(re.findall(r'@([a-zA-Z0-9_]+)', content))
    mentioned = {u for u in mentioned if not content.split(f'@{u}')[0].endswith('&')}
    if exclude_username:
        mentioned.discard(exclude_username)
    return mentioned


def extract_role_mentions(content):
    return set(re.findall(r'@&([a-zA-Z0-9_]+)', content))


def get_ping_patterns_for_user(username, user_roles):
    patterns = [f"@{username}", f"@{username}@", f"@{username} "]
    for role in user_roles:
        patterns.extend([f"@&{role}", f"@&{role}@", f"@&{role} "])
    return patterns


def check_ping_in_content(content, ping_patterns):
    return any(pattern in content for pattern in ping_patterns)


def validate_role_mentions_permissions(content, sender_user_roles):
    mentioned_roles = extract_role_mentions(content)
    for mentioned_role in mentioned_roles:
        if not roles.role_exists(mentioned_role):
            continue
        if not roles.can_role_mention_role(sender_user_roles, mentioned_role):
            return False, f"You do not have permission to mention the '@&{mentioned_role}' role"
    return True, None


def get_message_pings(content, sender_user_roles):
    mentioned_users = extract_user_mentions(content)
    mentioned_roles = extract_role_mentions(content)

    valid_users = set()
    for username in mentioned_users:
        user_id = users.get_id_by_username(username)
        if user_id:
            valid_users.add(users.get_username_by_id(user_id))
        else:
            valid_users.add(username)

    valid_roles = set()
    for role in mentioned_roles:
        if roles.role_exists(role) and roles.can_role_mention_role(sender_user_roles, role):
            valid_roles.add(role)
        elif not roles.role_exists(role):
            valid_roles.add(role)

    return {"users": list(valid_users), "roles": list(valid_roles), "replies": []}
