"""
AI Commit Analysis Package.

Modules:
- core: Configuration, data loading, git operations
- utils: Parsers, external tools, code smell detection
- metrics: Basic, complexity, security, survival metrics
- analyzers: Debt and lifecycle analysis

Usage:
    from src.core import ROOT_DIR, load_commits
    from src.analyzers import analyze_commit_debt, analyze_commit_lifecycle
"""

from src.core.config import ROOT_DIR

__version__ = "0.2.0"
__all__ = ["ROOT_DIR"]
