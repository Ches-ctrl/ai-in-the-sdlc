"""
Dev Companion Client
A lightweight Python client for monitoring development sessions and executing remote commands.
"""

__version__ = "1.0.0"
__author__ = "Dev Companion Team"

from .client import DevCompanionClient
from .config import Config

__all__ = ['DevCompanionClient', 'Config']