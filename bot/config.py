"""
Configuration for Polymarket Telegram Bot
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot token from @BotFather
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Optional: Allowed user IDs (comma-separated string)
ALLOWED_USER_IDS_STR = os.getenv('ALLOWED_USER_IDS', '')
ALLOWED_USER_IDS = [int(uid.strip()) for uid in ALLOWED_USER_IDS_STR.split(',') if uid.strip()]

# PolygonScan API Key (optional, for wallet_analyzer.py)
POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_API_KEY')

# Tracker configuration
TRACKER_TELEGRAM_CHAT_ID = os.getenv('TRACKER_TELEGRAM_CHAT_ID')
TRACKER_POLL_INTERVAL_SECONDS = int(os.getenv('TRACKER_POLL_INTERVAL_SECONDS', '15'))
TRACKER_TRIGGER_TOLERANCE_SECONDS = int(os.getenv('TRACKER_TRIGGER_TOLERANCE_SECONDS', '20'))
TRACKER_DATABASE_PATH = os.getenv('TRACKER_DATABASE_PATH', 'data/tracker.sqlite3')
TRACKER_DAILY_REPORT_HOUR_UTC = int(os.getenv('TRACKER_DAILY_REPORT_HOUR_UTC', '23'))
TRACKER_DRY_RUN = os.getenv('TRACKER_DRY_RUN', 'true').lower() in {'1', 'true', 'yes'}

# API endpoints for tracker
GAMMA_API_BASE_URL = os.getenv('GAMMA_API_BASE_URL', 'https://gamma-api.polymarket.com')
CLOB_API_BASE_URL = os.getenv('CLOB_API_BASE_URL', 'https://clob.polymarket.com')

# Rate limiting configuration
MAX_ANALYSES_PER_USER_PER_HOUR = 12  # 1 every 5 minutes
CACHE_DURATION_SECONDS = 3600  # Cache results for 1 hour

# Chart generation settings
CHART_DPI = 150  # Balance between quality and file size
CHART_FORMAT = 'png'

# Telegram message limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024


def is_user_allowed(user_id: int) -> bool:
    """
    Check if user is allowed to use the bot

    Args:
        user_id: Telegram user ID

    Returns:
        True if user is allowed (or no whitelist configured)
    """
    if not ALLOWED_USER_IDS:
        # No whitelist configured, allow everyone
        return True

    return user_id in ALLOWED_USER_IDS


def validate_config():
    """Validate that required configuration is present"""
    if not BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable not set. "
            "Copy .env.example to .env and add your bot token from @BotFather"
        )

    print("✓ Configuration loaded successfully")
    if ALLOWED_USER_IDS:
        print(f"  - User whitelist enabled: {len(ALLOWED_USER_IDS)} allowed users")
    else:
        print("  - User whitelist disabled: All users allowed")
