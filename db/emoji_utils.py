import emoji


def is_valid_emoji(emoji_str):
    """
    Check if a string is a valid emoji (or multiple emojis with no other content).

    Args:
        emoji_str (str): The string to check.

    Returns:
        bool: True if the string contains only emojis, False otherwise.
    """
    if not emoji_str:
        return False
    if emoji.emoji_count(emoji_str) == 0:
        return False
    return emoji.replace_emoji(emoji_str, '') == ''
