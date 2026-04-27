"""
Code Destiny Analysis - Track what happens to AI-generated code over time.

Tracks at TWO LEVELS:

1. SYNTACTIC (Line-level):
   - Which lines were added by AI
   - How many times each line was modified
   - Which lines were deleted
   - Line-based survival rate

2. SEMANTIC (AST-level):
   - Which functions/classes were added
   - Whether they still exist (possibly refactored)
   - Semantic survival rate (more robust to formatting changes)
"""

import subprocess
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from src.metrics.semantic_survival import analyze_file_semantic_survival
from src.filters import classify_path, is_noise_path, detect_language

logger = logging.getLogger(__name__)


def run_git(repo_dir: Path, args: list[str]) -> Tuple[int, str, str]:
    """Run git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "Git not found"


def get_commit_additions(repo_dir: Path, sha: str) -> Dict[str, List[Tuple[int, int]]]:
    """
    Get all lines ADDED in a commit, organized by file.
    
    Returns:
        Dict mapping file paths to list of (start_line, end_line) tuples
    """
    # Get the diff showing only added lines with line numbers
    # Handle root commits (no parent) by using --root flag
    returncode, diff_output, stderr = run_git(repo_dir, [
        "diff", "-U0", f"{sha}^..{sha}", "--"
    ])
    
    # If parent doesn't exist (root commit), use diff-tree instead
    if returncode != 0 or "unknown revision" in stderr.lower():
        returncode, diff_output, _ = run_git(repo_dir, [
            "show", "--format=", "-U0", sha, "--"
        ])
    
    if not diff_output:
        return {}
    
    additions = {}
    current_file = None
    
    for line in diff_output.split("\n"):
        # Detect file change
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if current_file not in additions:
                additions[current_file] = []
        
        # Parse hunk header: @@ -old,count +new,count @@
        elif line.startswith("@@") and current_file:
            # Extract the +new,count part
            parts = line.split()
            for part in parts:
                if part.startswith("+") and "," in part:
                    # Format: +start,count
                    nums = part[1:].split(",")
                    start = int(nums[0])
                    count = int(nums[1]) if len(nums) > 1 else 1
                    if count > 0:
                        additions[current_file].append((start, start + count - 1))
                elif part.startswith("+") and part[1:].isdigit():
                    # Format: +start (single line)
                    start = int(part[1:])
                    additions[current_file].append((start, start))
    
    return additions


# Cache resolved HEAD file content to avoid repeated git calls per line
_head_file_cache: Dict[str, Optional[str]] = {}


def _get_file_at_head(repo_dir: Path, filepath: str) -> Optional[str]:
    """Get file content at HEAD with rename resolution and caching."""
    if filepath in _head_file_cache:
        return _head_file_cache[filepath]
    
    # Try direct path first
    _, content, _ = run_git(repo_dir, ["show", f"HEAD:{filepath}"])
    if content:
        _head_file_cache[filepath] = content
        return content
    
    # File not at original path -- try rename detection via git log --follow
    try:
        rc, log_output, _ = run_git(repo_dir, [
            "log", "--follow", "--diff-filter=R", "--name-status",
            "--format=", "-1", "HEAD", "--", filepath
        ])
        for line in (log_output or "").splitlines():
            parts = line.strip().split("\t")
            if len(parts) == 3 and parts[0].startswith("R"):
                new_path = parts[2]
                _, new_content, _ = run_git(repo_dir, ["show", f"HEAD:{new_path}"])
                if new_content:
                    logger.debug("Rename detected: %s -> %s", filepath, new_path)
                    _head_file_cache[filepath] = new_content
                    return new_content
    except Exception:
        pass
    
    _head_file_cache[filepath] = None
    return None


def check_line_exists_at_head(repo_dir: Path, filepath: str, line_num: int, original_content: str) -> str:
    """
    Check if a specific line still exists at HEAD.
    
    Instead of checking by position (which breaks when lines shift),
    we search for the exact content anywhere in the current file.
    Follows renames so renamed files aren't falsely reported as deleted.
    
    Returns: "EXISTS" | "MODIFIED" | "DELETED"
    """
    original_stripped = original_content.strip()
    
    # Skip empty/whitespace-only lines
    if not original_stripped:
        return "EXISTS"  # Don't count empty lines as deleted
    
    # Get current file content at HEAD (with rename resolution)
    content = _get_file_at_head(repo_dir, filepath)
    
    if not content:
        return "DELETED"  # File was truly deleted (not just renamed)
    
    # Search for the exact line content anywhere in the current file
    # OPTIMIZATION: Check plain string inclusion first (fastest)
    if original_stripped not in content:
        return "MODIFIED" # Definitely gone/changed
        
    # Search for the exact line content line-by-line (to be sure)
    current_lines = content.splitlines()
    for current_line in current_lines:
        if current_line.strip() == original_stripped:
            return "EXISTS"
    
    # Content not found - check if file still exists but line was modified/removed
    return "MODIFIED"


def count_line_modifications(repo_dir: Path, sha: str, filepath: str, start: int, end: int) -> int:
    """
    Count how many times the lines were modified after the commit.
    
    Uses git log -L to trace line history.
    
    PERFORMANCE SAFETY:
    git log -L can be extremely slow on large ranges or deep history.
    If range is > 500 lines, skip detailed tracing to prevent pipeline hangs.
    """
    # Safety check for massive hunks (e.g. large copy-pastes)
    if end - start > 500:
        logger.debug(f"Skipping line tracing for massive hunk {filepath}:{start}-{end} (>500 lines)")
        return 0

    # Use git log -L to track line range
    _, log_output, _ = run_git(repo_dir, [
        "log", "--oneline", 
        "-L", f"{start},{end}:{filepath}",
        f"{sha}..HEAD",
        "--"
    ])
    
    if not log_output:
        return 0
    
    # Count commit hashes (one per line change)
    commits = set()
    for line in log_output.splitlines():
        # Commit lines are short hashes followed by message
        parts = line.strip().split()
        if parts and len(parts[0]) >= 7 and len(parts[0]) <= 12:
            commits.add(parts[0])
    
    return len(commits)


def analyze_code_destiny(
    repo_dir: Path,
    sha: str,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Analyze what happened to code added in an AI commit.
    
    Args:
        repo_dir: Path to repository
        sha: Commit SHA to analyze
        debug: Include detailed line info
        
    Returns:
        Dictionary with destiny metrics
    """
    # Clear the per-commit HEAD file cache
    _head_file_cache.clear()
    
    # Get all additions from this commit
    additions = get_commit_additions(repo_dir, sha)
    
    # Count will be updated after filtering
    result = {
        "commit": sha[:12],
        "files_analyzed": 0,  # Will be updated after filtering code files
        # Syntactic (line-level) metrics
        "total_lines_added": 0,
        "lines_still_exist": 0,
        "lines_modified": 0,
        "lines_deleted": 0,
        "total_modifications": 0,
        "survival_rate": 0.0,  # Syntactic survival
        "modification_rate": 0.0,
        "deletion_rate": 0.0,
        # Semantic (AST-level) metrics
        "semantic_units_original": 0,
        "semantic_units_surviving": 0,
        "semantic_units_modified": 0,
        "semantic_units_deleted": 0,
        "semantic_survival_rate": 0.0,
        "exact_semantic_survival_rate": 0.0,
        "semantic_vs_syntactic_delta": 0.0,
    }
    
    file_details = []
    semantic_details = []  # Track semantic analysis per file
    
    for filepath, line_ranges in additions.items():
        # Skip non-production code (tests, docs, configs, examples, etc.)
        if is_noise_path(filepath):
            continue
        if classify_path(filepath) != "code":
            continue
        # Must be a supported language
        if detect_language(filepath) == "other":
            continue
        
        file_info = {
            "file": filepath,
            "line_ranges": line_ranges,
            "lines_added": 0,
            "lines_exist": 0,
            "lines_modified": 0,
            "lines_deleted": 0,
            "modification_count": 0,
        }
        
        # Get original file content at commit
        _, original_content, _ = run_git(repo_dir, ["show", f"{sha}:{filepath}"])
        if not original_content:
            continue
            
        original_lines = original_content.splitlines()
        
        for start, end in line_ranges:
            for line_num in range(start, end + 1):
                if line_num > len(original_lines):
                    continue
                    
                file_info["lines_added"] += 1
                result["total_lines_added"] += 1
                
                original_line = original_lines[line_num - 1] if line_num > 0 else ""
                
                # Check line status
                status = check_line_exists_at_head(repo_dir, filepath, line_num, original_line)
                
                if status == "EXISTS":
                    file_info["lines_exist"] += 1
                    result["lines_still_exist"] += 1
                elif status == "MODIFIED":
                    file_info["lines_modified"] += 1
                    result["lines_modified"] += 1
                else:
                    file_info["lines_deleted"] += 1
                    result["lines_deleted"] += 1
        
        # Count total modifications to file
        for start, end in line_ranges:
            mod_count = count_line_modifications(repo_dir, sha, filepath, start, end)
            file_info["modification_count"] += mod_count
            result["total_modifications"] += mod_count
        
        # Calculate file-level syntactic survival for semantic comparison
        file_syntactic_rate = 0.0
        if file_info["lines_added"] > 0:
            file_syntactic_rate = file_info["lines_exist"] / file_info["lines_added"]
        
        # Semantic analysis: Compare AST structure (rename-aware)
        current_content = _get_file_at_head(repo_dir, filepath)
        
        if original_content and current_content:
            try:
                semantic_result = analyze_file_semantic_survival(
                    original_content,
                    current_content,
                    filepath,
                    syntactic_survival_rate=file_syntactic_rate,
                    tracked_line_ranges=line_ranges,
                )
                
                if semantic_result.get("supported"):
                    file_info["semantic"] = semantic_result
                    semantic_details.append({
                        "file": filepath,
                        **semantic_result
                    })
                    
                    # Aggregate semantic metrics
                    result["semantic_units_original"] += semantic_result.get("original_units", 0)
                    result["semantic_units_surviving"] += semantic_result.get("surviving_units", 0)
                    result["semantic_units_modified"] += semantic_result.get("modified_units", 0)
                    result["semantic_units_deleted"] += semantic_result.get("deleted_units", 0)
            except Exception as e:
                logger.debug("Semantic analysis failed for %s: %s", filepath, e)
        
        file_details.append(file_info)
        result["files_analyzed"] += 1  # Count actual code files analyzed
    
    # Calculate syntactic rates
    if result["total_lines_added"] > 0:
        result["survival_rate"] = round(
            result["lines_still_exist"] / result["total_lines_added"], 3
        )
        result["modification_rate"] = round(
            result["lines_modified"] / result["total_lines_added"], 3
        )
        result["deletion_rate"] = round(
            result["lines_deleted"] / result["total_lines_added"], 3
        )
    
    # Calculate semantic rates
    if result["semantic_units_original"] > 0:
        # Semantic survival = units that exist in any form (exact + modified)
        surviving_total = result["semantic_units_surviving"] + result["semantic_units_modified"]
        result["semantic_survival_rate"] = round(
            surviving_total / result["semantic_units_original"], 3
        )
        # Exact survival = units with identical structure
        result["exact_semantic_survival_rate"] = round(
            result["semantic_units_surviving"] / result["semantic_units_original"], 3
        )
        # Delta between semantic and syntactic
        result["semantic_vs_syntactic_delta"] = round(
            result["semantic_survival_rate"] - result["survival_rate"], 3
        )
    
    # Compute developer valuation based on semantic survival (more accurate)
    valuation_rate = result["semantic_survival_rate"] if result["semantic_units_original"] > 0 else result["survival_rate"]
    if valuation_rate >= 0.8:
        result["developer_valuation"] = "HIGH"
    elif valuation_rate >= 0.5:
        result["developer_valuation"] = "MEDIUM"
    else:
        result["developer_valuation"] = "LOW"
    
    # Always include file details for dashboard
    result["file_details"] = file_details
    
    # Include semantic details if any
    if semantic_details:
        result["semantic_details"] = semantic_details
    
    return result
