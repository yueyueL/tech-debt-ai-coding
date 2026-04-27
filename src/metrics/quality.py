"""
File quality analysis module.

Analyzes complete files using linters and quality tools,
returning structured results for before/after comparison.
"""

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.tools import (
    run_pylint, run_eslint, run_radon_cc, run_radon_mi,
    run_cognitive_complexity, run_njsscan, run_sonarqube,
    run_semgrep_security
)
from src.metrics.complexity import compute_cognitive_complexity
from src.metrics.security import is_semgrep_available
from src.utils.code_smells import (
    count_todos,
    count_fixmes,
)


# Max file size to analyze (1MB) - prevent stalling on massive generated files
MAX_FILE_SIZE_BYTES = 1024 * 1024


def analyze_file_quality(
    content: str,
    language: str,
    file_ext: str = "",
    debug: bool = False,
    sonarqube_only: bool = False,
    source_path: str = "",
) -> Dict[str, Any]:
    """
    Analyze quality of a complete file.
    
    Args:
        content: Full file content
        language: Programming language (python, javascript, typescript)
        file_ext: File extension for temp file (e.g., '.py', '.js')
        debug: Include detailed issue list
        sonarqube_only: If True, skip other analyzers and only use SonarQube
        
    Returns:
        Dictionary with quality metrics and optionally detailed issues
    """
    # Safety check for massive files
    if len(content.encode('utf-8')) > MAX_FILE_SIZE_BYTES:
        return {
            "lines": len(content.splitlines()),
            "issues_total": 0,
            "skipped": True,
            "reason": "File too large"
        }

    # Detect minified/bundled files for JS/TS.
    # Common traits: very long lines, huge size-to-linecount ratio, no whitespace.
    # Analyzing these produces hundreds of false positives (e.g., eqeqeq on line 1).
    if language in ("javascript", "typescript"):
        file_size = len(content)
        line_count = content.count("\n") + 1
        first_newline = content.find("\n")
        first_line_len = first_newline if first_newline != -1 else file_size

        is_minified = False
        reason = ""

        # Check 1: First line extremely long (>5000 chars = entire library on one line)
        if first_line_len > 5000:
            is_minified = True
            reason = f"Minified/bundled file (first line {first_line_len:,} chars)"

        # Check 2: Very high bytes-per-line ratio (e.g., 500KB file with <20 lines)
        # Normal code averages ~40-80 chars/line. Bundled code is often >1000 chars/line.
        elif file_size > 10000 and line_count > 0:
            avg_line_len = file_size / line_count
            if avg_line_len > 500:
                is_minified = True
                reason = f"Bundled file (avg {avg_line_len:.0f} chars/line across {line_count} lines)"

        if is_minified:
            return {
                "lines": line_count,
                "issues_total": 0,
                "skipped": True,
                "reason": reason,
            }

    lines = content.splitlines()
    result: Dict[str, Any] = {
        "lines": len(lines),
        "issues_total": 0,
    }
    issues: List[Dict[str, Any]] = []
    ext = file_ext or _get_extension(language)
    
    # If SonarQube-only mode, skip other analyzers
    if not sonarqube_only:
        # Simple code smell metrics (fast, no external tools)
        result["todos"] = count_todos(lines)
        result["fixmes"] = count_fixmes(lines)
        
        # Language-specific analysis
        if language == "python":
            result.update(_analyze_python(content, debug, issues, source_path=source_path))
        elif language in {"javascript", "typescript"}:
            ext = file_ext or (".ts" if language == "typescript" else ".js")
            result.update(_analyze_javascript(content, ext, debug, issues, source_path=source_path))
        
        # Calculate total issues
        result["issues_total"] = (
            result.get("linter_errors", 0) +
            result.get("linter_warnings", 0) +
            result.get("security_total", 0)
        )
    
    # SonarQube analysis - ONLY when sonarqube_only mode is enabled
    # This is slow (~30s) so only use when specifically requested
    if sonarqube_only:
        try:
            ext = file_ext or _get_extension(language)
            # Use /tmp for Docker accessibility on macOS (default uses /var/folders which Docker can't mount)
            with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False, dir="/tmp") as sonar_temp:
                sonar_temp.write(content)
                sonar_temp_path = Path(sonar_temp.name)
            
            try:
                sonar_metrics = run_sonarqube(sonar_temp_path)
                if sonar_metrics:
                    result["sonar"] = sonar_metrics
                    # Add SonarQube metrics to main result
                    if "cognitive_complexity" in sonar_metrics:
                        result["sonar_cognitive_complexity"] = sonar_metrics["cognitive_complexity"]
                    if "bugs" in sonar_metrics:
                        result["sonar_bugs"] = sonar_metrics["bugs"]
                    if "vulnerabilities" in sonar_metrics:
                        result["sonar_vulnerabilities"] = sonar_metrics["vulnerabilities"]
                    if "code_smells" in sonar_metrics:
                        result["sonar_code_smells"] = sonar_metrics["code_smells"]
            finally:
                sonar_temp_path.unlink(missing_ok=True)
        except Exception:
            pass  # SonarQube is optional - silently continue if it fails
    
    if debug:
        result["issues"] = issues
    
    return result


def _get_extension(language: str) -> str:
    """Get file extension for language."""
    extensions = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
    }
    return extensions.get(language, ".txt")


def _analyze_python(
    content: str,
    debug: bool,
    issues: List[Dict],
    source_path: str = "",
) -> Dict[str, Any]:
    """Run Python-specific analysis."""
    result: Dict[str, Any] = {}

    # IMPORTANT (defensibility): run analyzers on a path that resembles the repo
    # layout to reduce context-dependent false positives.
    #
    # Example: pylint's `relative-beyond-top-level` is often an artifact when a
    # file with relative imports is analyzed as a standalone temp file.
    work_dir = Path(tempfile.mkdtemp())
    rel = source_path.strip().lstrip("/").replace("\\", "/")
    if rel and rel.endswith(".py"):
        temp_path = work_dir / rel
    else:
        temp_path = work_dir / "temp.py"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(content, encoding="utf-8", errors="replace")

    # If the file uses relative imports, create minimal package scaffolding
    # so pylint doesn't treat it as a top-level script.
    has_relative_import = bool(re.search(r"^\s*from\s+\.+", content, flags=re.MULTILINE))
    if has_relative_import and rel and "/" in rel:
        p = temp_path.parent
        while p != work_dir:
            init_file = p / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")
            p = p.parent

    try:
        # Pylint analysis
        if debug:
            score, errors, warnings, messages = run_pylint(temp_path, detailed=True)
            for msg in messages:
                issues.append({
                    "type": "pylint",
                    "severity": msg.get("type", "warning"),
                    "line": msg.get("line"),
                    "symbol": msg.get("symbol"),
                    "message": msg.get("message"),
                    "category": "maintainability",  # Issue categorization
                })
        else:
            score, errors, warnings = run_pylint(temp_path)
        
        result["pylint_score"] = score
        result["linter_errors"] = errors
        result["linter_warnings"] = warnings
        result["cyclomatic_complexity"] = run_radon_cc(temp_path)
        result["maintainability_index"] = run_radon_mi(temp_path)
        
        # NEW: Cognitive complexity (from CursorStudy research)
        result["cognitive_complexity"] = run_cognitive_complexity(temp_path)
        
        # Security analysis via Semgrep only (Bandit fallback removed —
        # the paper's headline numbers are Semgrep-sourced and Bandit's
        # Python-only coverage inflates low-severity noise).
        if is_semgrep_available():
            if debug:
                sec_summary, sec_issues = run_semgrep_security(temp_path, detailed=True)
                for sec in sec_issues:
                    issues.append({
                        "type": "security",
                        "severity": sec.get("severity", "medium").lower(),
                        "line": sec.get("line_start"),
                        "symbol": sec.get("rule"),
                        "message": sec.get("message"),
                        "category": "vulnerability",
                        "detected_by": "semgrep",
                    })
                sec_high = sec_summary.get("error_count", 0)
                sec_med = sec_summary.get("warning_count", 0)
                sec_low = sec_summary.get("info_count", 0)
            else:
                sec_summary = run_semgrep_security(temp_path)
                sec_high = sec_summary.get("error_count", 0)
                sec_med = sec_summary.get("warning_count", 0)
                sec_low = sec_summary.get("info_count", 0)
        else:
            sec_high = sec_med = sec_low = 0
        
        result["security_high"] = sec_high
        result["security_medium"] = sec_med
        result["security_low"] = sec_low
        result["security_total"] = sec_high + sec_med + sec_low
        
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    
    return result


def _analyze_javascript(
    content: str,
    ext: str,
    debug: bool,
    issues: List[Dict],
    source_path: str = "",
) -> Dict[str, Any]:
    """Run JavaScript/TypeScript-specific analysis."""
    result: Dict[str, Any] = {}
    
    with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False) as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    
    try:
        # ESLint linting
        if debug:
            errors, warnings, messages = run_eslint(temp_path, detailed=True)
            for msg in messages:
                issues.append({
                    "type": "eslint",
                    "severity": msg.get("severity", "warning"),
                    "line": msg.get("line"),
                    "rule": msg.get("rule"),
                    "message": msg.get("message"),
                    "category": "maintainability",
                    "detected_by": "eslint",
                })
        else:
            errors, warnings = run_eslint(temp_path)
        
        result["linter_errors"] = errors
        result["linter_warnings"] = warnings
        result["console_logs"] = len(re.findall(r"\bconsole\.log\b", content))
        result["ts_any"] = len(re.findall(r"\bany\b", content)) if ext == ".ts" else 0
        result["ts_ignore"] = len(re.findall(r"@ts-ignore", content))

        # Cognitive complexity for JS/TS (Tier-1, lightweight; no external deps)
        result["cognitive_complexity"] = compute_cognitive_complexity(content)
        
        # NEW: Security analysis via Semgrep (preferred) or njsscan (fallback)
        use_semgrep = is_semgrep_available()
        
        if use_semgrep:
            if debug:
                sec_summary, sec_issues = run_semgrep_security(temp_path, detailed=True)
                for sec in sec_issues:
                    issues.append({
                        "type": "security",
                        "severity": sec.get("severity", "medium").lower(),
                        "line": sec.get("line_start"),
                        "symbol": sec.get("rule"),
                        "message": sec.get("message"),
                        "category": "vulnerability",
                        "detected_by": "semgrep",
                    })
                sec_high = sec_summary.get("error_count", 0)
                sec_med = sec_summary.get("warning_count", 0)
                sec_low = sec_summary.get("info_count", 0)
            else:
                sec_summary = run_semgrep_security(temp_path)
                sec_high = sec_summary.get("error_count", 0)
                sec_med = sec_summary.get("warning_count", 0)
                sec_low = sec_summary.get("info_count", 0)
        elif debug:
            sec_high, sec_med, sec_low, sec_issues = run_njsscan(temp_path, detailed=True)
            for sec in sec_issues:
                issues.append({
                    "type": "security",
                    "severity": sec.get("severity", "medium"),
                    "line": sec.get("line"),
                    "symbol": sec.get("rule"),
                    "message": sec.get("message"),
                    "category": "vulnerability",
                    "detected_by": "njsscan",
                })
        else:
            sec_high, sec_med, sec_low = run_njsscan(temp_path)
        
        result["security_high"] = sec_high
        result["security_medium"] = sec_med
        result["security_low"] = sec_low
        result["security_total"] = sec_high + sec_med + sec_low
        
    finally:
        temp_path.unlink(missing_ok=True)
    
    return result


def compute_quality_delta(
    before: Optional[Dict[str, Any]],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute the delta between before and after quality metrics.
    
    Negative values = improvement (fewer issues)
    Positive values = degradation (more issues)
    
    Args:
        before: Quality metrics before (None if file was added)
        after: Quality metrics after
        
    Returns:
        Delta dictionary with changes
    """
    if before is None:
        # New file - all issues are "introduced"
        return {
            "is_new_file": True,
            "issues_introduced": after.get("issues_total", 0),
            "issues_fixed": 0,
            "net_change": after.get("issues_total", 0),
            "linter_errors_delta": after.get("linter_errors", 0),
            "linter_warnings_delta": after.get("linter_warnings", 0),
            # NEW: Security deltas
            "security_high_delta": after.get("security_high", 0),
            "security_medium_delta": after.get("security_medium", 0),
            "security_low_delta": after.get("security_low", 0),
            "security_total_delta": after.get("security_total", 0),
            # NEW: Cognitive complexity  
            "cognitive_complexity_delta": after.get("cognitive_complexity", 0),
        }
    
    delta = {
        "is_new_file": False,
        "linter_errors_delta": (
            after.get("linter_errors", 0) - before.get("linter_errors", 0)
        ),
        "linter_warnings_delta": (
            after.get("linter_warnings", 0) - before.get("linter_warnings", 0)
        ),
        "duplicates_delta": after.get("duplicates", 0) - before.get("duplicates", 0),
        # NEW: Security deltas
        "security_high_delta": (
            after.get("security_high", 0) - before.get("security_high", 0)
        ),
        "security_medium_delta": (
            after.get("security_medium", 0) - before.get("security_medium", 0)
        ),
        "security_low_delta": (
            after.get("security_low", 0) - before.get("security_low", 0)
        ),
        "security_total_delta": (
            after.get("security_total", 0) - before.get("security_total", 0)
        ),
        # NEW: Cognitive complexity
        "cognitive_complexity_delta": (
            after.get("cognitive_complexity", 0) - before.get("cognitive_complexity", 0)
        ),
    }
    
    # Net change in total issues
    after_total = after.get("issues_total", 0)
    before_total = before.get("issues_total", 0)
    delta["net_change"] = after_total - before_total
    
    # FIXED: Track introduced AND fixed separately (not derived from net)
    # This is a rough estimate - actual counts come from issue matching in debt.py
    # But we provide reasonable defaults here for direct callers
    # 
    # Key insight: A commit can BOTH introduce AND fix issues simultaneously!
    # Example: Refactoring that fixes 5 old issues but introduces 3 new ones
    # Old broken logic: net = -2, so issues_introduced = 0, issues_fixed = 2
    # New correct logic: Track both - will be overwritten by issue matching if available
    #
    # For estimation when detailed matching isn't done:
    # - If after > before: we introduced (after - before), possibly fixed some too
    # - If before > after: we fixed (before - after), possibly introduced some too
    # - These are MINIMUM estimates; actual matching may find cross-changes
    delta["issues_introduced"] = max(0, after_total - before_total)
    delta["issues_fixed"] = max(0, before_total - after_total)
    
    # Flag to indicate these are estimates (debt.py will override with actual counts)
    delta["_counts_are_estimates"] = True
    
    # Quality improved/degraded
    delta["quality_improved"] = delta["net_change"] < 0
    delta["quality_degraded"] = delta["net_change"] > 0
    
    return delta
