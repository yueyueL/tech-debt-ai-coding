"""
Unified deep scan orchestration: run_deep_scan, analyze_commit_deep, analyze_ai_commits_deep.
"""

import json
import logging
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.gitops import list_changed_files_with_status, get_changed_lines
from src.metrics.deep_scan.availability import is_codeql_available, is_sonarqube_available
from src.metrics.deep_scan.codeql import run_codeql_analysis
from src.metrics.deep_scan.sonarqube import run_sonarqube_analysis

logger = logging.getLogger(__name__)


def run_deep_scan(
    repo_dir: Path,
    language: str,
    tools: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run comprehensive deep scan using all available tools.

    Args:
        repo_dir: Path to the repository
        language: Primary language of the repository
        tools: List of tools to use (default: all available)
               Options: ["codeql", "sonarqube"]

    Returns:
        Combined results from all tools
    """
    # Convert to absolute path (required for Docker volume mounts)
    repo_dir = Path(repo_dir).resolve()

    if tools is None:
        tools = ["codeql", "sonarqube"]

    results = {
        "tools_used": [],
        "repo": str(repo_dir),
        "language": language,
    }

    total_issues = 0
    security_issues = 0
    quality_issues = 0
    all_issues = []

    # Run CodeQL
    if "codeql" in tools and is_codeql_available():
        logger.info(f"Running CodeQL analysis on {repo_dir}...")
        codeql_result = run_codeql_analysis(repo_dir, language)
        if codeql_result:
            results["codeql"] = codeql_result
            results["tools_used"].append("codeql")
            total_issues += codeql_result.get("issue_count", 0)
            for issue in codeql_result.get("issues", []):
                if issue.get("type") == "security":
                    security_issues += 1
                else:
                    quality_issues += 1
                all_issues.append({**issue, "source": "codeql"})

    # Run SonarQube
    if "sonarqube" in tools and is_sonarqube_available():
        logger.info(f"Running SonarQube analysis on {repo_dir}...")
        sonar_result = run_sonarqube_analysis(repo_dir)
        if sonar_result:
            results["sonarqube"] = sonar_result
            results["tools_used"].append("sonarqube")
            total_issues += sonar_result.get("issue_count", 0)
            for issue in sonar_result.get("issues", []):
                if issue.get("type") in ["vulnerability", "security hotspot"]:
                    security_issues += 1
                else:
                    quality_issues += 1
                all_issues.append({**issue, "source": "sonarqube"})

    # Combine results
    results["combined"] = {
        "total_issues": total_issues,
        "security_issues": security_issues,
        "quality_issues": quality_issues,
        "all_issues": all_issues,
    }

    return results


# =============================================================================
# COMMIT-LEVEL DEEP SCAN (Before/After Comparison)
# =============================================================================

def analyze_commit_deep(
    repo_dir: Path,
    commit_sha: str,
    language: str,
    tools: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Analyze a single commit with before/after comparison using deep scan tools.

    This is the KEY function for research - it identifies issues INTRODUCED by
    a specific commit by comparing the state before and after.

    Args:
        repo_dir: Path to the repository
        commit_sha: The commit SHA to analyze
        language: Primary language of the repository
        tools: List of tools to use (default: all available)

    Returns:
        {
            "commit": "sha",
            "issues_before": [...],
            "issues_after": [...],
            "issues_introduced": [...],  # New issues in this commit
            "issues_fixed": [...],       # Issues resolved by this commit
            "net_change": int,
        }
    """
    import subprocess as sp

    repo_dir = Path(repo_dir).resolve()

    if tools is None:
        tools = []
        if is_codeql_available():
            tools.append("codeql")
        if is_sonarqube_available():
            tools.append("sonarqube")

    if not tools:
        logger.warning("No deep scan tools available for commit analysis")
        return {"commit": commit_sha, "error": "No tools available"}

    # Get parent commit
    result = sp.run(
        ["git", "rev-parse", f"{commit_sha}^"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )
    parent_sha = result.stdout.strip() if result.returncode == 0 else None

    # Get list of files changed in this commit (with status to handle renames)
    changed_files_status = list_changed_files_with_status(repo_dir, commit_sha)
    changed_files = {path for path, _ in changed_files_status}

    # Store current HEAD
    result = sp.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), capture_output=True, text=True)
    original_head = result.stdout.strip()

    issues_before = []
    issues_after = []

    try:
        # Checkout parent and scan BEFORE state
        if parent_sha:
            logger.info(f"Analyzing BEFORE state (parent: {parent_sha[:8]})")
            sp.run(["git", "checkout", "-q", parent_sha], cwd=str(repo_dir), check=True)
            before_results = run_deep_scan(repo_dir, language, tools)
            issues_before = before_results.get("combined", {}).get("all_issues", [])

        # Checkout commit and scan AFTER state
        logger.info(f"Analyzing AFTER state (commit: {commit_sha[:8]})")
        sp.run(["git", "checkout", "-q", commit_sha], cwd=str(repo_dir), check=True)
        after_results = run_deep_scan(repo_dir, language, tools)
        issues_after = after_results.get("combined", {}).get("all_issues", [])

    finally:
        # Restore original HEAD
        sp.run(["git", "checkout", "-q", original_head], cwd=str(repo_dir))

    # Compare: find issues introduced and fixed
    # Use FUZZY MATCHING to handle line shifts
    LINE_TOLERANCE = 5  # Allow ±5 lines for same issue match

    def get_issue_identity(issue):
        """Identity without line - for grouping similar issues."""
        return (
            issue.get("file", ""),
            issue.get("rule", issue.get("rule_id", "")),
            issue.get("message", "")[:100],
        )

    def issues_match_fuzzy(issue1, issue2, tolerance=LINE_TOLERANCE):
        """Check if two issues are the same (allowing line shift)."""
        if get_issue_identity(issue1) != get_issue_identity(issue2):
            return False
        line1 = int(issue1.get("line", 0))
        line2 = int(issue2.get("line", 0))
        if line1 == 0 or line2 == 0:
            return True
        return abs(line1 - line2) <= tolerance

    # Group issues by identity (file + rule + message)
    before_by_id = defaultdict(list)
    after_by_id = defaultdict(list)

    for issue in issues_before:
        before_by_id[get_issue_identity(issue)].append(issue)
    for issue in issues_after:
        after_by_id[get_issue_identity(issue)].append(issue)

    # Match issues with fuzzy line tolerance
    matched_before = set()
    matched_after = set()

    all_ids = set(before_by_id.keys()) | set(after_by_id.keys())

    for identity in all_ids:
        bef_list = sorted(before_by_id[identity], key=lambda x: int(x.get("line", 0)))
        aft_list = sorted(after_by_id[identity], key=lambda x: int(x.get("line", 0)))

        # Greedy matching by line proximity
        for i, bef in enumerate(bef_list):
            if (identity, i) in matched_before:
                continue
            for j, aft in enumerate(aft_list):
                if (identity, j) in matched_after:
                    continue
                if issues_match_fuzzy(bef, aft):
                    matched_before.add((identity, i))
                    matched_after.add((identity, j))
                    break

    # Filter to only issues in changed files AND on changed lines
    issues_introduced = []
    file_changed_lines = {}  # cache

    for identity in all_ids:
        aft_list = after_by_id[identity]
        for j, issue in enumerate(aft_list):
            if (identity, j) in matched_after:
                continue  # This issue existed before (matched)

            # New issue - check if in changed files
            issue_file = issue.get("file", "")
            if issue_file not in changed_files and changed_files:
                continue

            # STRICT ACCURACY: Check if issue is on a changed line
            if issue_file not in file_changed_lines:
                file_changed_lines[issue_file] = get_changed_lines(repo_dir, commit_sha, issue_file)

            issue_line = issue.get("line", 0)
            if issue_line == 0 or issue_line in file_changed_lines[issue_file]:
                issues_introduced.append(issue)

    issues_fixed = []
    for identity in all_ids:
        bef_list = before_by_id[identity]
        for i, issue in enumerate(bef_list):
            if (identity, i) in matched_before:
                continue  # This issue still exists (matched)

            issue_file = issue.get("file", "")
            if issue_file in changed_files or not changed_files:
                issues_fixed.append(issue)

    return {
        "commit": commit_sha,
        "parent": parent_sha,
        "files_changed": list(changed_files),
        "issues_before_count": len(issues_before),
        "issues_after_count": len(issues_after),
        "issues_introduced": issues_introduced,
        "issues_fixed": issues_fixed,
        "issues_introduced_count": len(issues_introduced),
        "issues_fixed_count": len(issues_fixed),
        "net_change": len(issues_introduced) - len(issues_fixed),
        "tools_used": tools,
    }


def analyze_ai_commits_deep(
    repo_dir: Path,
    commits: List[Dict[str, Any]],
    language: str,
    tools: Optional[List[str]] = None,
    limit: int = 0,
) -> Dict[str, Any]:
    """
    Analyze multiple AI commits with before/after comparison.

    This is the main entry point for deep scanning AI commits from an input JSON.

    Args:
        repo_dir: Path to the repository
        commits: List of commit dicts with 'sha' or 'commit_hash' keys
        language: Primary language of the repository
        tools: List of tools to use
        limit: Max commits to analyze (0 = all)

    Returns:
        Aggregated results with per-commit details
    """
    repo_dir = Path(repo_dir).resolve()

    if limit > 0 and limit < len(commits):
        commits = commits[:limit]

    results = {
        "repo": str(repo_dir),
        "language": language,
        "commits_analyzed": len(commits),
        "total_issues_introduced": 0,
        "total_issues_fixed": 0,
        "net_change": 0,
        "commits": [],
        "all_introduced_issues": [],
    }

    for i, commit in enumerate(commits, 1):
        sha = commit.get("sha", commit.get("commit_hash", ""))
        if not sha:
            continue

        logger.info(f"[{i}/{len(commits)}] Deep scanning commit {sha[:8]}...")

        try:
            commit_result = analyze_commit_deep(repo_dir, sha, language, tools)
            results["commits"].append(commit_result)

            introduced = commit_result.get("issues_introduced_count", 0)
            fixed = commit_result.get("issues_fixed_count", 0)

            results["total_issues_introduced"] += introduced
            results["total_issues_fixed"] += fixed
            results["net_change"] += commit_result.get("net_change", 0)
            results["all_introduced_issues"].extend(commit_result.get("issues_introduced", []))

            if introduced > 0:
                logger.info(f"  Found {introduced} new issues, {fixed} fixed")

        except Exception as e:
            logger.warning(f"  Error analyzing {sha[:8]}: {e}")
            results["commits"].append({
                "commit": sha,
                "error": str(e),
            })

    # Summary by severity/type
    by_severity = {}
    by_type = {}
    for issue in results["all_introduced_issues"]:
        sev = issue.get("severity", "unknown").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1

        itype = issue.get("type", "unknown")
        by_type[itype] = by_type.get(itype, 0) + 1

    results["summary"] = {
        "total_introduced": results["total_issues_introduced"],
        "total_fixed": results["total_issues_fixed"],
        "net_change": results["net_change"],
        "by_severity": by_severity,
        "by_type": by_type,
    }

    return results
