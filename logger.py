class Colors:
    """ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Standard colors
    DARKGREEN = '\033[32m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'

class Logger:
    """Enhanced logger with ANSI colors and symbols"""
    @staticmethod
    def distinct(message: str):
        """Log a distinct message with a unique symbol"""
        print(f"{Colors.GREEN}[~]{Colors.RESET} {message}")


    @staticmethod
    def add(message: str):
        """Log an addition/creation action"""
        print(f"{Colors.GREEN}[+]{Colors.RESET} {message}")
    
    @staticmethod
    def edit(message: str):
        """Log an edit/modification action"""
        print(f"{Colors.YELLOW}[~]{Colors.RESET} {message}")
    
    @staticmethod
    def delete(message: str):
        """Log a deletion action"""
        print(f"{Colors.RED}[x]{Colors.RESET} {message}")
    
    @staticmethod
    def get(message: str):
        """Log a retrieval/query action"""
        print(f"{Colors.BLUE}[?]{Colors.RESET} {message}")
    
    @staticmethod
    def info(message: str):
        """Log general information"""
        print(f"{Colors.CYAN}[i]{Colors.RESET} {message}")
    
    @staticmethod
    def warning(message: str):
        """Log warnings"""
        print(f"{Colors.YELLOW}[!]{Colors.RESET} {message}")
    
    @staticmethod
    def error(message: str):
        """Log errors"""
        print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}")
    
    @staticmethod
    def success(message: str):
        """Log success messages"""
        print(f"{Colors.GREEN}[✓]{Colors.RESET} {message}")

    @staticmethod
    def discordupdate(message: str):
        """Log Discord update messages"""
        print(f"{Colors.YELLOW}[☺]{Colors.RESET} {message}")
    
    @staticmethod
    def discord_message(username: str, message: str):
        """Log Discord messages with special formatting"""
        print(f"{Colors.GREEN}[+]{Colors.RESET} Discord Message | {Colors.CYAN}{username}{Colors.RESET}: {message}")
