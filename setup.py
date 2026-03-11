import os, json, sys, shutil
from logger import Logger
from config_builder import DEFAULT_CONFIG, build_config

# OriginChats Setup Script
Logger.info("Starting OriginChats server configuration...")

def get_input(prompt, default=None):
    """Get user input with optional default value"""
    if default:
        user_input = input(f"{prompt} [Default: {default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()

def yes_no(prompt, default="y"):
    """Get yes/no input from user"""
    while True:
        response = input(f"{prompt} [{default}]: ").strip().lower()
        if not response:
            response = default
        if response in ["y", "yes", "true", "1"]:
            return True
        elif response in ["n", "no", "false", "0"]:
            return False
        print("Please enter y/n")

def setup_directories():
    """Create necessary directories if they don't exist"""
    directories = ["db", "db/backup", "db/serverAssets", "db/serverEmojis"]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            Logger.add(f"Created directory: {directory}")

def _prepare_server_asset_input(prompt_text):
    candidate = get_input(prompt_text).strip()
    if not candidate:
        return None

    assets_dir = os.path.join(os.path.dirname(__file__), "db", "serverAssets")
    os.makedirs(assets_dir, exist_ok=True)

    if os.path.dirname(candidate):
        source = os.path.normpath(candidate)
        if not os.path.isabs(source):
            source = os.path.normpath(os.path.join(os.getcwd(), source))
        if not os.path.isfile(source):
            Logger.warning(f"Server asset not found at {candidate}")
            return None
        dest = os.path.join(assets_dir, os.path.basename(source))
        shutil.copy2(source, dest)
        return os.path.basename(source)

    target = os.path.join(assets_dir, candidate)
    if not os.path.isfile(target):
        Logger.warning(f"Server asset not found in db/serverAssets: {candidate}")
        return None
    return candidate


def main():
    """Main setup function"""
    print()
    print("=" * 50)
    print("        OriginChats Server Setup")
    print("=" * 50)
    print()
    
    # Check if config already exists
    config_exists = os.path.exists("config.json")
    if config_exists:
        if not yes_no("Config file already exists. Overwrite?", "n"):
            Logger.warning("Setup cancelled")
            return
    
    print("Let's configure your OriginChats server...")
    print()
    
    # Server configuration
    print("--- Server Configuration ---")
    server_name = get_input("Server name", DEFAULT_CONFIG["server"]["name"])
    print("Server assets directory (/db/serverAssets/) ready. You can now enter either a source file path or an existing filename from the folder...")
    server_icon = _prepare_server_asset_input("Server icon filename or source path (optional)")
    server_banner = _prepare_server_asset_input("Server banner filename or source path (optional)")
    server_url = get_input("Server URL (optional, used for hosted icon/banner links)")
    owner_name = get_input("Server owner name", DEFAULT_CONFIG["server"]["owner"]["name"])
    
    print()
    print("--- WebSocket Configuration ---")
    ws_host = get_input("WebSocket host", DEFAULT_CONFIG["websocket"]["host"])
    ws_port = get_input("WebSocket port", str(DEFAULT_CONFIG["websocket"]["port"]))
    
    try:
        ws_port = int(ws_port)
    except ValueError:
        Logger.warning(f"Invalid port number, using default {DEFAULT_CONFIG['websocket']['port']}")
        ws_port = DEFAULT_CONFIG["websocket"]["port"]
    
    print()
    print("--- Content Limits ---")
    max_message_length = get_input("Maximum message length", str(DEFAULT_CONFIG["limits"]["post_content"]))
    search_results_limit = get_input("Search results limit", str(DEFAULT_CONFIG["limits"]["search_results"]))
    
    try:
        max_message_length = int(max_message_length)
    except ValueError:
        print(f"[OriginChats Setup] Invalid length, using default {DEFAULT_CONFIG['limits']['post_content']}")
        max_message_length = DEFAULT_CONFIG["limits"]["post_content"]

    try:
        search_results_limit = int(search_results_limit)
    except ValueError:
        print(f"[OriginChats Setup] Invalid search limit, using default {DEFAULT_CONFIG['limits']['search_results']}")
        search_results_limit = DEFAULT_CONFIG["limits"]["search_results"]

    print()
    print("--- Upload Rules ---")
    emoji_file_types_csv = get_input(
        "Allowed emoji file extensions (CSV)",
        ",".join(DEFAULT_CONFIG["uploads"]["emoji_allowed_file_types"]),
    )
    emoji_allowed_file_types = [
        ext.strip().lower().lstrip(".")
        for ext in emoji_file_types_csv.split(",")
        if ext.strip()
    ]
    if not emoji_allowed_file_types:
        print("[OriginChats Setup] No valid emoji file extensions provided, using defaults")
        emoji_allowed_file_types = DEFAULT_CONFIG["uploads"]["emoji_allowed_file_types"]

    config = build_config({
        "server": {
            "name": server_name,
            "owner": {
                "name": owner_name,
            },
            "icon": server_icon or None,
            "banner": server_banner or None,
            "url": server_url or None,
        },
        "websocket": {
            "host": ws_host,
            "port": ws_port,
        },
        "limits": {
            "post_content": max_message_length,
            "search_results": search_results_limit,
        },
        "uploads": {
            "emoji_allowed_file_types": emoji_allowed_file_types,
        },
    })
    
    # Create directories and files
    print()
    print("--- Setting up directories and files ---")
    setup_directories()
    
    # Write config file
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
    
    print()
    print("=" * 50)
    print("[OriginChats Setup] Configuration complete!")
    print()
    print("Your server is configured with:")
    print(f"  Server Name: {server_name}")
    print(f"  WebSocket: {ws_host}:{ws_port}")
    print(f"  Owner: {owner_name}")
    print()
    print("To start your server, run:")
    print("  python init.py")
    print()
    print("Make sure to:")
    print("1. Configure your Rotur validation key properly")
    print("2. Set up any firewall rules for your WebSocket port")
    print("3. Configure SSL/TLS if running in production")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        Logger.warning("Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        Logger.error(f"Error during setup: {str(e)}")
        sys.exit(1)
