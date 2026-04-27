"""
CLI entry point for AI Code Quality Research Tool.

Re-exports ``main`` so existing ``from src.cli import main`` continues to work.
"""

from src.cli.main import main
from src.cli.colors import Colors

__all__ = ["main", "Colors"]
