#!/usr/bin/env python3
"""Command-line interface for Dev Companion."""

import asyncio
import sys
import signal
import logging
import argparse
from pathlib import Path

from .client import DevCompanionClient
from .config import Config


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main entry point for the dev-companion command."""
    parser = argparse.ArgumentParser(
        description="Monitor Claude Code sessions and execute remote commands"
    )
    
    parser.add_argument(
        "--api-url",
        help="API base URL (overrides DEV_COMPANION_API_BASE_URL)",
        default=None
    )
    
    parser.add_argument(
        "--ws-url", 
        help="WebSocket URL (overrides DEV_COMPANION_WS_URL)",
        default=None
    )
    
    parser.add_argument(
        "--token",
        help="API token (overrides DEV_COMPANION_API_TOKEN)",
        default=None
    )
    
    parser.add_argument(
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
        default=None
    )
    
    parser.add_argument(
        "--project",
        help="Project path to monitor (defaults to current directory)",
        default=None
    )
    
    parser.add_argument(
        "--env-file",
        help="Path to .env file (defaults to ./.env)",
        default=".env"
    )
    
    args = parser.parse_args()
    
    # Load .env file if it exists
    env_path = Path(args.env_file)
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
    
    # Override with command-line arguments
    import os
    if args.api_url:
        os.environ['DEV_COMPANION_API_BASE_URL'] = args.api_url
    if args.ws_url:
        os.environ['DEV_COMPANION_WS_URL'] = args.ws_url
    if args.token:
        os.environ['DEV_COMPANION_API_TOKEN'] = args.token
    if args.log_level:
        os.environ['DEV_COMPANION_LOG_LEVEL'] = args.log_level
    if args.project:
        os.environ['DEV_COMPANION_MONITORED_PROJECTS'] = args.project
    
    # Load configuration
    config = Config()
    
    # Setup logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)
    
    # Create client
    client = DevCompanionClient(config)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        pass  # Shutting down
        asyncio.create_task(client.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the client
    # Starting Dev Companion
    
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        pass  # Stopped by user
    except Exception as e:
        logger.error(f"Dev Companion error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()