"""Main entry point for the translation service.

This file serves as the entry point for Gunicorn.
All application logic is in the src/ package.
"""

from src.app import app

__all__ = ["app"]
