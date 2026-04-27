"""
Debt analysis for AI-authored commits.

Uses before/after comparison to measure quality changes.
"""

import logging
import threading
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from src.core.gitops import (
    get_commit_parent,
    get_file_at_commit,
    list_changed_files_with_status,
    get_changed_lines,
)
from src.filters import detect_language, get_language_extension, classify_path, is_noise_path
from src.metrics.quality import analyze_file_quality, compute_quality_delta
from src.metrics.security import run_semgrep, is_semgrep_available
from src.config.blocked_rules import get_issue_filter_context, is_issue_low_signal


logger = logging.getLogger(__name__)

# Default number of parallel workers for file analysis
DEFAULT_WORKERS = 4


@dataclass
class AnalysisCounters:
    """Track files skipped, analyzed, and errored during debt analysis."""
    files_total: int = 0
    files_analyzed: int = 0
    files_skipped_deleted: int = 0
    files_skipped_noise: int = 0
    files_skipped_non_code: int = 0
    files_skipped_language: int = 0
    files_skipped_generated: int = 0
    files_skipped_vendored: int = 0
    files_skipped_too_large: int = 0
    files_skipped_example: int = 0
    files_errored: int = 0
    files_no_content: int = 0

    def to_dict(self) -> Dict[str, Any]:
        skipped_total = (
            self.files_skipped_deleted + self.files_skipped_noise +
            self.files_skipped_non_code + self.files_skipped_language +
            self.files_skipped_generated + self.files_skipped_vendored +
            self.files_skipped_too_large + self.files_skipped_example
        )
        return {
            "files_total": self.files_total,
            "files_analyzed": self.files_analyzed,
            "files_skipped": {
                "total": skipped_total,
                "deleted": self.files_skipped_deleted,
                "noise": self.files_skipped_noise,
                "non_code": self.files_skipped_non_code,
                "unsupported_language": self.files_skipped_language,
                "generated": self.files_skipped_generated,
                "vendored": self.files_skipped_vendored,
                "too_large": self.files_skipped_too_large,
                "example": self.files_skipped_example,
            },
            "files_errored": self.files_errored,
            "files_no_content": self.files_no_content,
        }


def classify_skip_reason(file_path: str) -> Optional[str]:
    """
    Return the skip reason for a file, or None if it should be analyzed.

    Reasons: 'noise', 'non_code', 'unsupported_language', 'example',
             'generated', 'vendored'
    """
    if is_noise_path(file_path):
        return "noise"

    category = classify_path(file_path)
    if category != "code":
        return "non_code"

    language = detect_language(file_path)
    SUPPORTED_LANGUAGES = {"python", "javascript", "typescript"}
    if language not in SUPPORTED_LANGUAGES:
        return "unsupported_language"

    path_lower = file_path.lower()

    if any(x in path_lower for x in ['/example', '/demo', '/sample', '/tutorial', '/playground']):
        return "example"

    generated_patterns = [
        '/generated/', '/gen/', '/_generated/', '.generated.',
        '.pb.go', '.g.dart', '_generated.rs', '.auto.ts',
    ]
    if any(x in path_lower for x in generated_patterns):
        return "generated"

    if any(x in path_lower for x in ['/vendor/', '/third_party/', '/external/', '/deps/']):
        return "vendored"

    return None


def should_analyze_file(file_path: str) -> bool:
    """
    Check if file should be included in debt analysis.
    
    IMPORTANT: Only analyze PRODUCTION CODE.
    Skip tests, docs, configs, data files, etc.
    
    ACTUALLY SUPPORTED languages (have real analyzers):
    - Python (.py) - pylint, bandit, radon, semgrep
    - JavaScript (.js, .jsx) - eslint, njsscan, semgrep
    - TypeScript (.ts, .tsx) - eslint, semgrep
    
    NOTE: Other languages (Go, Java, Rust, etc.) are detected but NOT analyzed
    because we don't have quality analyzers for them. Including them would
    produce false "clean" signals that bias research results.
    """
    if is_noise_path(file_path):
        return False
    
    # Classify the file path
    category = classify_path(file_path)
    
    # STRICT: Only analyze production code
    # Skip: tests, docs, data, config, examples, other
    if category != "code":
        return False
    
    # HONEST LANGUAGE SUPPORT: Only analyze languages we have real analyzers for
    language = detect_language(file_path)
    # These are the ONLY languages with actual quality analyzers in quality.py
    SUPPORTED_LANGUAGES = {"python", "javascript", "typescript"}
    if language not in SUPPORTED_LANGUAGES:
        return False
    
    # Additional exclusions for research accuracy
    path_lower = file_path.lower()
    
    # Skip example/demo/sample code (all languages)
    if any(x in path_lower for x in ['/example', '/demo', '/sample', '/tutorial', '/playground']):
        return False
    
    # Skip generated code (all languages)
    generated_patterns = [
        '/generated/', '/gen/', '/_generated/', '.generated.',
        '.pb.go',        # Go protobuf
        '.g.dart',       # Dart generated
        '_generated.rs', # Rust generated
        '.auto.ts',      # TypeScript auto-generated
    ]
    if any(x in path_lower for x in generated_patterns):
        return False
    
    # Skip vendored/copied code (not authored by AI)
    if any(x in path_lower for x in ['/vendor/', '/third_party/', '/external/', '/deps/']):
        return False
    
    return True


def _match_issues(
    before_issues: List[Dict[str, Any]], 
    after_issues: List[Dict[str, Any]], 
    changed_lines: set
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Smartly match issues between before/after states to handle:
    1. Line shifts (insertions/deletions elsewhere in file)
    2. Duplicate issues (same rule/message multiple times)
    3. Strict attribution (only count introduced if on changed lines)
    
    Returns: (issues_added, issues_resolved)
    """
    # Group by identity (excluding line number)
    def get_id(issue):
        return (
            issue.get("type", ""),
            issue.get("rule", issue.get("symbol", "")),
            issue.get("message", ""),
        )
        
    before_map = defaultdict(list)
    after_map = defaultdict(list)
    
    for i in before_issues:
        before_map[get_id(i)].append(i)
    for i in after_issues:
        after_map[get_id(i)].append(i)
        
    added = []
    resolved = []
    
    all_keys = set(before_map.keys()) | set(after_map.keys())
    
    for k in all_keys:
        bef = sorted(before_map[k], key=lambda x: int(x.get("line", 0)))
        aft = sorted(after_map[k], key=lambda x: int(x.get("line", 0)))
        
        # Track indices matched
        matched_bef = set()
        matched_aft = set()
        
        # 1. Exact Match (Same Line)
        for i, b in enumerate(bef):
            if i in matched_bef: continue
            for j, a in enumerate(aft):
                if j in matched_aft: continue
                if int(b.get("line", 0)) == int(a.get("line", 0)):
                    matched_bef.add(i)
                    matched_aft.add(j)
                    break
        
        # 2. Fuzzy Match (Nearest Neighbor for shifts)
        # Handles cases where code shifted down/up but issue persists
        # FIXED: Added MAX_LINE_DISTANCE cap to prevent false matches across large files
        MAX_LINE_DISTANCE = 40  # Issues > 40 lines apart are treated as different
        # Rationale: 40 lines ≈ one function. If an issue "moved" further than that,
        # it's almost certainly a different occurrence, not a line-shift of the same issue.
        
        for i, b in enumerate(bef):
            if i in matched_bef: continue
            
            best_j = -1
            best_dist = float('inf')
            b_line = int(b.get("line", 0))
            
            for j, a in enumerate(aft):
                if j in matched_aft: continue
                dist = abs(int(a.get("line", 0)) - b_line)
                # FIXED: Enforce 100-line threshold (was mentioned in comment but not implemented)
                # If issue moved > 100 lines, treat as new issue (likely different context)
                if dist < best_dist and dist <= MAX_LINE_DISTANCE:
                    best_dist = dist
                    best_j = j
            
            if best_j != -1:
                matched_bef.add(i)
                matched_aft.add(best_j)
                
        # Collect unmatched (Added / Resolved)
        for j, a in enumerate(aft):
            if j not in matched_aft:
                # FILTER: Only count as "Introduced" if on a changed line
                line = int(a.get("line", 0))
                
                # 1. Line Check — strict attribution to changed lines only.
                # FIXED: When changed_lines is empty (diff parse failure, pure deletion),
                # do NOT fall through to "accept all". Only accept if:
                #   a) line==0 (linter couldn't determine line → keep for safety), or
                #   b) changed_lines is non-empty AND line is in it, or
                #   c) changed_lines is a special sentinel _ALL_LINES (root commits
                #      where every line is new)
                if changed_lines:
                    # Normal case: only count if issue is on a changed line
                    is_relevant = (line == 0 or line in changed_lines)
                else:
                    # Empty set → diff parse failed or pure deletion.
                    # Conservative: skip this issue (don't attribute to commit).
                    # line==0 means linter couldn't pin it to a line, keep those.
                    is_relevant = (line == 0)
                
                if is_relevant:
                    added.append(a)
                    
        for i, b in enumerate(bef):
            if i not in matched_bef:
                resolved.append(b)
                
    return added, resolved


def _analyze_single_file(
    args: Tuple[str, str, Path, str, Optional[str], bool, bool]
) -> Optional[Dict[str, Any]]:
    """
    Analyze a single file for quality metrics.
    
    This function is designed to run in parallel via ThreadPoolExecutor.
    
    Args:
        args: Tuple of (file_path, status, repo_dir, sha, parent_sha, debug, sonarqube_only)
        
    Returns:
        Dictionary with file analysis result, or None if file should be skipped
    """
    file_path, status, repo_dir, sha, parent_sha, debug, sonarqube_only = args
    
    # Skip deleted files
    if status == "D":
        return None
    
    language = detect_language(file_path)
    file_ext = get_language_extension(language)
    
    # Get file content before and after
    before_content = None
    after_content = None
    
    if status == "A":
        # File was added - no "before" content
        before_content = None
        after_content = get_file_at_commit(repo_dir, sha, file_path)
    else:
        # File was modified
        if parent_sha:
            before_content = get_file_at_commit(repo_dir, parent_sha, file_path)
        after_content = get_file_at_commit(repo_dir, sha, file_path)
    
    if after_content is None:
        logger.debug("Could not get file content for %s at %s", file_path, sha[:8])
        return None
    
    # Analyze quality before and after
    before_quality = None
    if before_content is not None:
        before_quality = analyze_file_quality(
            before_content,
            language,
            file_ext,
            debug=True,
            sonarqube_only=sonarqube_only,
            source_path=file_path,
        )
    
    after_quality = analyze_file_quality(
        after_content,
        language,
        file_ext,
        debug=True,
        sonarqube_only=sonarqube_only,
        source_path=file_path,
    )
    
    # Compute delta
    delta = compute_quality_delta(before_quality, after_quality)
    # Preserve the raw delta (not line-attributed) for debugging/research transparency.
    # The fields we overwrite below (issues_introduced/fixed/net_change) are the
    # STRICT, line-attributed values based on matched issue lists.
    raw_delta = delta.copy()
    
    before_filter_context = get_issue_filter_context(
        file_path=file_path,
        file_content=before_content,
    )
    after_filter_context = get_issue_filter_context(
        file_path=file_path,
        file_content=after_content,
    )

    # Build result
    file_result = {
        "file_path": file_path,
        "language": language,
        "status": status,
        "issue_filter_context_before": before_filter_context,
        "issue_filter_context_after": after_filter_context,
        "before": _simplify_metrics(before_quality) if before_quality else None,
        "after": _simplify_metrics(after_quality),
        "delta": delta,
    }
    
    # Collect issue details - show what CHANGED (added/resolved)
    before_issues = before_quality.get("issues", []) if before_quality else []
    after_issues = after_quality.get("issues", [])
    
    # Calculate changed lines for strict attribution
    changed_lines = get_changed_lines(repo_dir, sha, file_path)
    
    # SMART MATCHING: Handle line shifts and duplicates
    issues_added, issues_resolved = _match_issues(before_issues, after_issues, changed_lines)

    # Preserve raw findings, but mark style-heavy / analyzer-artifact issues so
    # downstream views can hide them by default without losing the data.
    for issue in issues_added + issues_resolved:
        severity = str(issue.get("severity", "unknown")).lower()
        issue["_is_low_severity"] = (
            severity in ["low", "info", "style", "convention", "refactor"]
            or is_issue_low_signal(issue, file_path=file_path)
        )

    # Always include issue details in file result
    file_result["issues_added"] = issues_added
    file_result["issues_resolved"] = issues_resolved
    file_result["issues_added_count"] = len(issues_added)
    file_result["issues_resolved_count"] = len(issues_resolved)
    
    # Update delta with actual issue counts (not just net total)
    delta["issues_introduced"] = len(issues_added)
    delta["issues_fixed"] = len(issues_resolved)
    delta["net_change"] = len(issues_added) - len(issues_resolved)
    delta["quality_improved"] = len(issues_resolved) > len(issues_added)
    delta["quality_degraded"] = len(issues_added) > len(issues_resolved)
    # These counts are no longer estimates once we apply matching + line attribution.
    delta["_counts_are_estimates"] = False
    # Keep the pre-attribution delta for auditability.
    delta["_raw"] = raw_delta
    
    return file_result


def analyze_commit_debt(
    repo_dir: Path,
    sha: str,
    ai_tool: str,
    repo_name: str = "",
    debug: bool = False,
    sonarqube_only: bool = False,
    workers: int = DEFAULT_WORKERS,
) -> Dict:
    """
    Analyze a single commit for code debt metrics using before/after comparison.
    
    For each file changed in the commit:
    1. Get file content at parent commit (before)
    2. Get file content at this commit (after)
    3. Run quality analysis on both
    4. Compute delta (what changed)
    
    Uses parallel processing for analyzing multiple files simultaneously.
    
    Args:
        repo_dir: Path to the repository
        sha: Commit SHA to analyze
        ai_tool: AI tool that authored the commit
        repo_name: Repository name
        debug: If True, include detailed debug info
        sonarqube_only: If True, use only SonarQube analysis (skip other linters)
        
    Returns:
        Dictionary with per-file quality metrics and deltas
    """
    parent_sha = get_commit_parent(repo_dir, sha)
    
    try:
        changed_files = list_changed_files_with_status(repo_dir, sha)
    except RuntimeError as exc:
        logger.warning("Failed to list files for %s: %s", sha, exc)
        return {
            "commit_hash": sha,
            "ai_tool": ai_tool,
            "repo": repo_name,
            "files": [],
            "error": str(exc),
        }

    # Filter to code files only, tracking skip reasons
    files_to_analyze = []
    counters = AnalysisCounters()
    counters.files_total = len(changed_files)

    for file_path, status in changed_files:
        if status == "D":
            counters.files_skipped_deleted += 1
            continue
        reason = classify_skip_reason(file_path)
        if reason is None:
            files_to_analyze.append((file_path, status, repo_dir, sha, parent_sha, debug, sonarqube_only))
        else:
            _REASON_ATTR = {
                "noise": "files_skipped_noise",
                "non_code": "files_skipped_non_code",
                "unsupported_language": "files_skipped_language",
                "generated": "files_skipped_generated",
                "vendored": "files_skipped_vendored",
                "example": "files_skipped_example",
            }
            attr = _REASON_ATTR.get(reason)
            if attr:
                setattr(counters, attr, getattr(counters, attr) + 1)
    
    file_results = []
    debug_data = {}
    total_issues_introduced = 0
    total_issues_fixed = 0
    # Track issues by category for detailed reporting
    # FIXED: Use thread-safe Counter instead of regular dict for parallel access
    issues_by_type: Counter = Counter()
    issues_by_severity: Counter = Counter()
    
    # Thread lock for safe updates to shared state
    results_lock = threading.Lock()
    
    # Use parallel processing for file analysis
    if len(files_to_analyze) > 1 and workers > 1:
        # Parallel processing for multiple files
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_analyze_single_file, args): args[0] for args in files_to_analyze}
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        # FIXED: Use lock for thread-safe updates
                        with results_lock:
                            file_results.append(result)
                            delta = result.get("delta", {})
                            total_issues_introduced += delta.get("issues_introduced", 0)
                            total_issues_fixed += delta.get("issues_fixed", 0)
                            
                            # Track issues by type and severity (Counter is thread-safe for updates)
                            for issue in result.get("issues_added", []):
                                itype = issue.get("type", "unknown")
                                isev = issue.get("severity", "unknown")
                                issues_by_type[itype] += 1
                                issues_by_severity[isev] += 1
                            
                            # Debug data
                            if debug and (result.get("issues_added") or result.get("issues_resolved")):
                                debug_data[file_path] = {
                                    "issues_added": result.get("issues_added", []),
                                    "issues_resolved": result.get("issues_resolved", []),
                                }
                except Exception as e:
                    logger.warning("Error analyzing %s: %s", file_path, e)
                    with results_lock:
                        counters.files_errored += 1
    else:
        # Single file - no need for parallel overhead
        for args in files_to_analyze:
            result = _analyze_single_file(args)
            if result is not None:
                file_results.append(result)
                delta = result.get("delta", {})
                total_issues_introduced += delta.get("issues_introduced", 0)
                total_issues_fixed += delta.get("issues_fixed", 0)
                
                # Track issues by type and severity
                for issue in result.get("issues_added", []):
                    itype = issue.get("type", "unknown")
                    isev = issue.get("severity", "unknown")
                    issues_by_type[itype] += 1
                    issues_by_severity[isev] += 1
                
                if debug and (result.get("issues_added") or result.get("issues_resolved")):
                    debug_data[result["file_path"]] = {
                        "issues_added": result.get("issues_added", []),
                        "issues_resolved": result.get("issues_resolved", []),
                    }

    counters.files_analyzed = len(file_results)
    skipped_total = counters.to_dict()["files_skipped"]["total"]
    if skipped_total > 0:
        logger.debug("Skipped %d files in %s (analyzed %d)", skipped_total, sha[:8], counters.files_analyzed)

    result = {
        "commit_hash": sha,
        "ai_tool": ai_tool,
        "repo": repo_name,
        "code_files_analyzed": len(file_results),
        "analysis_counters": counters.to_dict(),
        "summary": {
            "total_issues_introduced": total_issues_introduced,
            "total_issues_fixed": total_issues_fixed,
            "net_change": total_issues_introduced - total_issues_fixed,
            "quality_improved": total_issues_fixed > total_issues_introduced,
            # Convert Counter to dict for JSON serialization
            "issues_by_type": dict(issues_by_type),
            "issues_by_severity": dict(issues_by_severity),
        },
        "files": file_results,
    }
    
    # Add debug info if present
    if debug and debug_data:
        result["_debug"] = debug_data
    
    return result


def _simplify_metrics(quality: Optional[Dict]) -> Dict:
    """Extract key metrics for output, keeping it clean."""
    if quality is None:
        return {}
    keys = [
        "lines", "linter_errors", "linter_warnings", "issues_total",
        "security_high", "security_medium", "security_low", "security_total",
        "cognitive_complexity", "cyclomatic_complexity", "maintainability_index",
        "pylint_score", "console_logs", "ts_any", "ts_ignore",
        "todos", "fixmes", "duplicates",
        "skipped", "reason",
    ]
    return {k: quality[k] for k in keys if k in quality}


def _clean_quality_for_output(quality: Dict) -> Dict:
    """Extract key metrics for output, excluding debug details."""
    return _simplify_metrics(quality)
