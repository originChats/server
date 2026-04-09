from typing import Any, Dict, Optional


def success(data: Dict[str, Any], cmd: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a success response.
    
    Args:
        data: Response data
        cmd: Optional command name to include
    
    Returns:
        Response dict with cmd and data
    """
    if cmd:
        data["cmd"] = cmd
    return data


def error(message: str, cmd: Optional[str] = None) -> Dict[str, Any]:
    """
    Create an error response.
    
    Args:
        message: Error message
        cmd: Optional source command name
    
    Returns:
        Error response dict
    """
    if cmd:
        return {"cmd": "error", "src": cmd, "val": message}
    return {"cmd": "error", "val": message}


def global_response(data: Dict[str, Any], cmd: str) -> Dict[str, Any]:
    """
    Create a global broadcast response.
    
    Args:
        data: Response data
        cmd: Command name
    
    Returns:
        Response dict with global=True flag
    """
    return {**data, "cmd": cmd, "global": True}


def channel_response(data: Dict[str, Any], cmd: str, channel: str) -> Dict[str, Any]:
    """
    Create a channel-specific broadcast response.
    
    Args:
        data: Response data
        cmd: Command name
        channel: Channel name
    
    Returns:
        Response dict with channel and global=True
    """
    return {**data, "cmd": cmd, "channel": channel, "global": True}


def pong_response() -> Dict[str, str]:
    """
    Create a pong response.
    
    Returns:
        Pong response dict
    """
    return {"cmd": "pong", "val": "pong"}
