"""
Shared data loading utilities for AI commit analysis.
"""

import json
from pathlib import Path
from typing import Iterable, List


def load_commits(path: Path) -> Iterable[dict]:
    """
    Load commits from JSON or JSONL file.
    
    Supports:
    - JSONL format: one commit per line (with per-commit tool attribution)
    - JSON array: list of commit objects (with per-commit tool attribution)
    - New JSON format: dict with ai_commits array (full commit details with ai_tool)
      Fields: sha, repo, ai_tool, detection_method, author_name, author_email, 
              message, date, url, author_role, ai_identifier, ai_identifier_type
    - Legacy JSON summary format: ai_commit_summary with ai_commit_shas array
      NOTE: This format lacks per-commit tool attribution, so tool is marked as 'unknown'
    """
    path = Path(path)
    
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            # New format: ai_commits array with full commit details
            # Each commit has: sha, repo, ai_tool, detection_method, author_name, etc.
            if "ai_commits" in data and isinstance(data.get("ai_commits"), list):
                commits: List[dict] = []
                repo_name = data.get("repo", "")
                for commit in data["ai_commits"]:
                    # Normalize fields to match expected format
                    commits.append({
                        "sha": commit.get("sha"),
                        "full_name": commit.get("repo") or repo_name,
                        "repo": commit.get("repo") or repo_name,
                        "ai_tool": commit.get("ai_tool", "unknown"),
                        "tool": commit.get("ai_tool", "unknown"),
                        "detection_method": commit.get("detection_method"),
                        "author_name": commit.get("author_name"),
                        "author_email": commit.get("author_email"),
                        "message": commit.get("message"),
                        "date": commit.get("date"),
                        "url": commit.get("url"),
                        "author_role": commit.get("author_role"),
                        "ai_identifier": commit.get("ai_identifier"),
                        "ai_identifier_type": commit.get("ai_identifier_type"),
                        # Derive repo_url from commit url or repo name
                        "repo_url": _extract_repo_url(commit.get("url")) or commit.get("repo") or repo_name,
                    })
                return commits
            
            # Legacy format: ai_commit_summary with ai_commit_shas array
            # NOTE: This format doesn't have per-commit tool attribution
            # The ai_tools field lists ALL tools used in the repo, not per-commit
            if "ai_commit_shas" in data:
                ai_tools = data.get("ai_tools") or []
                commits = []
                for sha in data.get("ai_commit_shas") or []:
                    commits.append({
                        "full_name": data.get("repo"),
                        "repo_url": data.get("repo_url") or data.get("repo_source"),
                        "sha": sha,
                        # Don't join all tools - we don't know which tool authored which commit
                        # Use first tool as best guess, or "unknown"
                        "tool": ai_tools[0] if len(ai_tools) == 1 else "unknown",
                        "possible_tools": ai_tools,  # Include all possible tools for reference
                    })
                return commits
        return []
    
    # JSONL format
    entries: List[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return entries


def _extract_repo_url(commit_url: str | None) -> str | None:
    """
    Extract repository URL from commit URL.
    
    Example:
        https://github.com/PostHog/posthog/commit/abc123 -> https://github.com/PostHog/posthog
    """
    if not commit_url:
        return None
    # Handle GitHub commit URLs
    if "/commit/" in commit_url:
        return commit_url.rsplit("/commit/", 1)[0]
    return None


def save_results(path: Path, data: dict | list, indent: int = 2) -> None:
    """Save results to JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=indent), encoding="utf-8")
