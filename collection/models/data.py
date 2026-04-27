"""
Unified data models for AI code collection.

Models:
- RepoStats: Repository-level statistics (for discover mode)
- CommitInfo: Basic commit record (for BigQuery)
- AICommit: Detailed AI commit (for repo scanning)
- RepoScanResult: Result of scanning a single repo
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class CommitInfo:
    """Individual commit record with AI attribution (from BigQuery)."""
    sha: str
    repo_name: str
    ai_tool: str
    detection_method: str  # "actor", "author", "coauthor"
    author_name: str = ""
    author_email: str = ""
    created_at: str = ""
    has_human_coauthor: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RepoStats:
    """Repository-level statistics for AI-authored commits."""
    full_name: str
    url: str
    stars: int = 0
    language: Optional[str] = None
    description: Optional[str] = None
    # Metadata fields
    is_fork: bool = False             # True if this repo is a fork of another
    parent: Optional[str] = None      # Parent repo full_name (if fork)
    fork_count: int = 0               # Number of forks OF this repo
    created_at: Optional[str] = None  # ISO timestamp
    pushed_at: Optional[str] = None   # Last push timestamp
    topics: List[str] = field(default_factory=list)
    # Commit tracking
    commit_counts: Dict[str, int] = field(default_factory=dict)
    commit_shas: Dict[str, List[str]] = field(default_factory=dict)
    detection_methods: Dict[str, str] = field(default_factory=dict)
    has_human_coauthor: bool = False
    
    @property
    def total_commits(self) -> int:
        return sum(self.commit_counts.values())
    
    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "url": self.url,
            "stars": self.stars,
            "language": self.language,
            "description": self.description,
            "is_fork": self.is_fork,
            "parent": self.parent,
            "fork_count": self.fork_count,
            "created_at": self.created_at,
            "pushed_at": self.pushed_at,
            "topics": self.topics,
            "commit_counts": self.commit_counts,
            "commit_shas": self.commit_shas,
            "detection_methods": self.detection_methods,
            "has_human_coauthor": self.has_human_coauthor,
            "total_commits": self.total_commits,
        }


@dataclass
class AICommit:
    """A commit detected as AI-authored (from repo scanning)."""
    sha: str
    repo: str
    ai_tool: str
    detection_method: str  # "actor", "author_name", "author_email", "coauthor"
    author_name: str
    author_email: str
    message: str
    date: str
    url: str
    
    # Author role - is AI the sole author or a co-author?
    author_role: str = ""  # "sole_author" | "coauthor"
    
    # What AI identifier matched (the pattern that triggered detection)
    ai_identifier: str = ""  # e.g., "claude[bot]", "noreply@anthropic.com"
    ai_identifier_type: str = ""  # "author_name" | "author_email" | "actor" | "coauthor_name" | "coauthor_email"
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RepoScanResult:
    """Result of scanning a repo for AI commits."""
    repo: str
    total_commits_scanned: int
    ai_commits: List[AICommit] = field(default_factory=list)
    tools_found: dict = field(default_factory=dict)  # tool -> count
    
    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "total_commits_scanned": self.total_commits_scanned,
            "ai_commits_count": len(self.ai_commits),
            "tools_found": self.tools_found,
            "ai_commits": [c.to_dict() for c in self.ai_commits],
        }
