"""
Lifecycle analysis for AI-authored commits.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.gitops import (
    run_git,
    get_commit_timestamp,
    list_commit_files,
)
from src.utils.parsers import parse_log_entries
from src.filters import classify_path, is_noise_path


logger = logging.getLogger(__name__)

FIX_PATTERNS = [
    re.compile(r"\bfix(?:es|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bbug(?:fix)?\b", re.IGNORECASE),
    re.compile(r"\bpatch(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bhotfix\b", re.IGNORECASE),
    re.compile(r"\bissue\b", re.IGNORECASE),
    re.compile(r"\bcleanup\b", re.IGNORECASE),
]

REFACTOR_PATTERNS = [
    re.compile(r"\brefactor(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bclean(?:up)?\b", re.IGNORECASE),
    re.compile(r"\brewrite\b", re.IGNORECASE),
    re.compile(r"\brework\b", re.IGNORECASE),
    re.compile(r"\bimprove(?:ment|d|s)?\b", re.IGNORECASE),
]

REVERT_PATTERNS = [
    re.compile(r"\brevert(?:ed|ing)?\b", re.IGNORECASE),
]


# File extensions to ignore in lifecycle analysis
IGNORE_EXTENSIONS = {
    ".json", ".lock", ".yaml", ".yml", ".toml", ".xml",  # Config/data
    ".md", ".rst", ".txt", ".adoc",  # Documentation
    ".svg", ".png", ".jpg", ".gif", ".ico",  # Images
    ".css", ".scss", ".less",  # Styles (often generated)
}

# File patterns to always ignore
IGNORE_PATTERNS = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Cargo.lock", "Gemfile.lock", "poetry.lock",
    "composer.lock", "go.sum",
    ".gitignore", ".gitattributes",
    "LICENSE", "CHANGELOG", "CONTRIBUTING",
}


def should_analyze_file(file_path: str) -> bool:
    """Check if file should be included in lifecycle analysis."""
    # Skip noise paths (node_modules, vendor, etc.)
    if is_noise_path(file_path):
        return False
    
    # Skip by pattern
    basename = Path(file_path).name
    if basename in IGNORE_PATTERNS:
        return False
    if basename.upper() in IGNORE_PATTERNS:
        return False
    
    # Skip by extension
    suffix = Path(file_path).suffix.lower()
    if suffix in IGNORE_EXTENSIONS:
        return False
    
    # Only analyze production code (skip tests, docs, etc.)
    category = classify_path(file_path)
    return category == "code"


def file_exists_at(repo_dir: Path, sha: str, file_path: str) -> bool:
    """Check if file exists at a given commit."""
    try:
        output = run_git(["ls-tree", "-r", "--name-only", sha, "--", file_path], cwd=repo_dir)
    except RuntimeError:
        return False
    return bool(output.strip())


def classify_changes(messages: List[Tuple[str, int]]) -> Dict:
    """Classify subsequent changes to AI code."""
    result = {
        "was_fixed": False,
        "was_refactored": False,
        "was_reverted": False,
        "num_subsequent_changes": len(messages),
        "time_to_first_fix": None,
        "time_to_first_refactor": None,
        "num_fix_commits": 0,
        "num_refactor_commits": 0,
        "num_revert_commits": 0,
    }
    for msg, ts in messages:
        if any(pattern.search(msg) for pattern in FIX_PATTERNS):
            result["was_fixed"] = True
            result["num_fix_commits"] += 1
            if result["time_to_first_fix"] is None:
                result["time_to_first_fix"] = ts
        if any(pattern.search(msg) for pattern in REFACTOR_PATTERNS):
            result["was_refactored"] = True
            result["num_refactor_commits"] += 1
            if result["time_to_first_refactor"] is None:
                result["time_to_first_refactor"] = ts
        if any(pattern.search(msg) for pattern in REVERT_PATTERNS):
            result["was_reverted"] = True
            result["num_revert_commits"] += 1
    return result


def analyze_commit_lifecycle(
    repo_dir: Path,
    sha: str,
    ai_tool: str,
    default_head: str,
    repo_name: str = "",
    debug: bool = False,
) -> Dict:
    """
    Analyze lifecycle of a single commit.
    
    Tracks what happened to AI-authored code over time:
    - SURVIVED: Code unchanged since AI commit  
    - MODIFIED: Code was changed by subsequent commits
    - DELETED: File was deleted
    
    Also tracks:
    - days_to_first_change: How long until first modification
    - was_fixed: Whether any changes were bug fixes
    - was_refactored: Whether code was refactored
    
    Args:
        repo_dir: Path to the repository
        sha: Commit SHA to analyze
        ai_tool: AI tool that authored the commit
        default_head: Default branch HEAD SHA
        repo_name: Repository name
        debug: If True, include detailed subsequent commit info
    """
    ai_ts = get_commit_timestamp(repo_dir, sha)
    all_file_paths = list_commit_files(repo_dir, sha)
    
    # Filter to code files only
    code_file_paths = [fp for fp in all_file_paths if should_analyze_file(fp)]
    skipped_files = len(all_file_paths) - len(code_file_paths)
    
    if skipped_files > 0:
        logger.debug("Skipped %d non-code files in %s", skipped_files, sha[:8])

    file_results = []
    debug_data = {}
    
    for file_path in code_file_paths:
        log_output = run_git(
            [
                "log",
                "--follow",
                '--format=%H|%an|%ae|%at|%s',
                f"{sha}..{default_head}",
                "--",
                file_path,
            ],
            cwd=repo_dir,
        )
        entries = parse_log_entries(log_output)
        messages = [(entry[4], entry[3]) for entry in entries]

        # Calculate days to first change
        days_to_first_change = None
        if entries and ai_ts:
            first_ts = entries[0][3]
            if first_ts > ai_ts:
                days_to_first_change = (first_ts - ai_ts) / 86400.0

        # Determine current status
        status = "SURVIVED"
        if not entries and not file_exists_at(repo_dir, default_head, file_path):
            status = "DELETED"
        elif entries:
            status = "MODIFIED"

        classification = classify_changes(messages)
        time_to_first_fix = None
        time_to_first_refactor = None
        if classification["time_to_first_fix"] and ai_ts:
            time_to_first_fix = (classification["time_to_first_fix"] - ai_ts) / 86400.0
        if classification["time_to_first_refactor"] and ai_ts:
            time_to_first_refactor = (classification["time_to_first_refactor"] - ai_ts) / 86400.0

        file_results.append({
            "filepath": file_path,
            "status": status,
            "days_to_first_change": days_to_first_change,
            "was_fixed": classification["was_fixed"],
            "was_refactored": classification["was_refactored"],
            "was_reverted": classification["was_reverted"],
            "was_deleted": status == "DELETED",
            "num_changes": classification["num_subsequent_changes"],
            "num_fix_commits": classification["num_fix_commits"],
            "num_refactor_commits": classification["num_refactor_commits"],
            "num_revert_commits": classification["num_revert_commits"],
            "time_to_first_fix_days": time_to_first_fix,
            "time_to_first_refactor_days": time_to_first_refactor,
        })
        
        # Capture debug info - subsequent commit details
        if debug and entries:
            subsequent_commits = []
            for commit_hash, author_name, author_email, ts, subject in entries:
                is_fix = any(pattern.search(subject) for pattern in FIX_PATTERNS)
                is_refactor = any(pattern.search(subject) for pattern in REFACTOR_PATTERNS)
                is_revert = any(pattern.search(subject) for pattern in REVERT_PATTERNS)
                subsequent_commits.append({
                    "sha": commit_hash,
                    "author": author_name,
                    "email": author_email,
                    "timestamp": ts,
                    "message": subject,
                    "is_fix": is_fix,
                    "is_refactor": is_refactor,
                    "is_revert": is_revert,
                })
            debug_data[file_path] = {
                "subsequent_commits": subsequent_commits
            }

    result = {
        "commit_hash": sha,
        "ai_tool": ai_tool,
        "repo": repo_name,
        "total_files_in_commit": len(all_file_paths),
        "code_files_analyzed": len(code_file_paths),
        "files": file_results,
    }
    
    if debug and debug_data:
        result["_debug"] = debug_data
    
    return result
