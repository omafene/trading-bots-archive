"""
Configuration loader with environment variable support
Safely loads config from YAML and overrides sensitive values with environment variables
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def load_env_file(env_path: str = ".env"):
    """Load environment variables from .env file if it exists"""
    env_file = Path(env_path)
    if not env_file.exists():
        logger.debug(f"No .env file found at {env_path}")
        return

    logger.info(f"Loading environment variables from {env_path}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                os.environ[key] = value


def load_config_with_env(config_path: str = "config_15m.yaml") -> Dict:
    """
    Load configuration from YAML file and override sensitive values with environment variables

    Priority:
    1. Environment variables (highest)
    2. .env file
    3. config YAML file (lowest)
    """

    # Load .env file first (if it exists)
    load_env_file()

    # Load base config from YAML
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Override sensitive values with environment variables
    # API Credentials
    if 'KALSHI_API_KEY_ID' in os.environ:
        config['api']['api_key_id'] = os.environ['KALSHI_API_KEY_ID']
        logger.info("✅ Using KALSHI_API_KEY_ID from environment")
    else:
        logger.warning("⚠️ KALSHI_API_KEY_ID not found in environment, using config file value")

    if 'KALSHI_PRIVATE_KEY_PATH' in os.environ:
        config['api']['private_key_path'] = os.environ['KALSHI_PRIVATE_KEY_PATH']
        logger.info("✅ Using KALSHI_PRIVATE_KEY_PATH from environment")

    # Telegram Credentials
    if config.get('telegram', {}).get('enabled', False):
        if 'TELEGRAM_BOT_TOKEN' in os.environ:
            config['telegram']['bot_token'] = os.environ['TELEGRAM_BOT_TOKEN']
            logger.info("✅ Using TELEGRAM_BOT_TOKEN from environment")
        else:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN not found in environment, using config file value")

        if 'TELEGRAM_CHAT_ID' in os.environ:
            config['telegram']['chat_id'] = os.environ['TELEGRAM_CHAT_ID']
            logger.info("✅ Using TELEGRAM_CHAT_ID from environment")

    return config
