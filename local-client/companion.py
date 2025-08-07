#!/usr/bin/env python3
"""
Dev Companion Client - Main entry point
Monitors development sessions and executes remote commands.
"""

import os
import sys
from dotenv import load_dotenv

from dev_companion import DevCompanionClient, __version__


def main():
    """Main entry point for Dev Companion Client."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Simple startup message
    print(f"Dev Companion Client v{__version__}")
    
    # Check for config file
    config_file = os.getenv('DEV_COMPANION_CONFIG_FILE', 'config.yaml')
    
    # Create and run client
    client = DevCompanionClient(config_file=config_file)
    
    # Run the client
    client.run()


if __name__ == '__main__':
    main()