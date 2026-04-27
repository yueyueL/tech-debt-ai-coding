"""
Collectors for AI-authored code.

- BigQueryCollector: Discover AI-authored repos via GitHub Archive
- GitHubFetcher: Fetch commit details from GitHub API
- GitCommitsCollector: Scan repos via git clone
- GitHubCommitsCollector: Scan repos via GitHub API
"""

from .bigquery import BigQueryCollector
from .github import GitHubFetcher
from .git_commits import GitCommitsCollector
from .github_commits import GitHubCommitsCollector

__all__ = [
    "BigQueryCollector",
    "GitHubFetcher",
    "GitCommitsCollector",
    "GitHubCommitsCollector",
]
