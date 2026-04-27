"""
Issue Survival Analysis Module.

Tracks whether issues introduced in AI commits survive over time.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.core.gitops import get_file_at_commit, resolve_file_at_head
from src.filters import detect_language
from src.metrics.quality import analyze_file_quality
from src.utils.tools.python_tools import run_bandit

logger = logging.getLogger(__name__)


def _normalize_rule_id(issue: Dict[str, Any]) -> str:
    return (
        str(
            issue.get("rule_id")
            or issue.get("rule")
            or issue.get("symbol")
            or issue.get("check_id")
            or issue.get("type")
            or "unknown"
        )
        .strip()
    )


def _normalize_message(message: Any) -> str:
    return " ".join(str(message or "").lower().split())


def _coerce_line(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _line_text(file_content: str, line_number: int) -> str:
    if not file_content or line_number <= 0:
        return ""
    lines = file_content.splitlines()
    if line_number > len(lines):
        return ""
    return lines[line_number - 1].strip()


def _normalize_line_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _line_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


def compute_issue_fingerprint(issue: Dict[str, Any], file_content: str) -> str:
    """
    Create a stable fingerprint for an issue that survives nearby line shifts.
    """
    rule_id = _normalize_rule_id(issue)
    line = _coerce_line(issue.get("line"))

    lines = file_content.splitlines()
    start = max(0, line - 4)
    end = min(len(lines), line + 3)
    context_lines = lines[start:end]
    normalized_context = "\n".join(_normalize_line_text(line) for line in context_lines)

    fingerprint_str = f"{rule_id}:{normalized_context}"
    return hashlib.md5(fingerprint_str.encode("utf-8")).hexdigest()


def _augment_python_issues_with_bandit(
    current_content: str,
    resolved_path: str,
    current_issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Re-run Bandit on HEAD when the original issue family is Bandit-specific.

    Semgrep is preferred in the main pipeline, but survival tracking for Python
    security issues needs Bandit as a supplemental source because Semgrep does
    not cover every Bandit rule family consistently.
    """
    work_dir = Path(tempfile.mkdtemp(prefix="issue-survival-bandit-"))
    rel = resolved_path.strip().lstrip("/").replace("\\", "/")
    temp_path = work_dir / rel if rel.endswith(".py") else work_dir / "temp.py"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(current_content, encoding="utf-8", errors="replace")

    try:
        _, _, _, bandit_issues = run_bandit(temp_path, detailed=True)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    seen = {
        (_normalize_rule_id(issue), _coerce_line(issue.get("line")), _normalize_message(issue.get("message")))
        for issue in current_issues
    }
    augmented = list(current_issues)
    for bandit_issue in bandit_issues:
        normalized = {
            "line": bandit_issue.get("line"),
            "severity": bandit_issue.get("severity", "medium"),
            "rule_id": bandit_issue.get("rule"),
            "rule": bandit_issue.get("rule"),
            "message": bandit_issue.get("message"),
            "type": bandit_issue.get("type", "security"),
            "detected_by": "bandit",
        }
        key = (
            _normalize_rule_id(normalized),
            _coerce_line(normalized.get("line")),
            _normalize_message(normalized.get("message")),
        )
        if key not in seen:
            augmented.append(normalized)
            seen.add(key)

    return augmented


def _score_issue_candidate(
    original_issue: Dict[str, Any],
    original_content: str,
    current_issue: Dict[str, Any],
    current_content: str,
) -> Tuple[float, str]:
    original_rule = _normalize_rule_id(original_issue)
    current_rule = _normalize_rule_id(current_issue)
    if original_rule != current_rule:
        return 0.0, "rule-mismatch"

    original_message = _normalize_message(original_issue.get("message"))
    current_message = _normalize_message(current_issue.get("message"))
    original_line = _coerce_line(original_issue.get("line"))
    current_line = _coerce_line(current_issue.get("line"))

    original_text = _normalize_line_text(_line_text(original_content, original_line))
    current_text = _normalize_line_text(_line_text(current_content, current_line))

    if original_text and current_text and original_text == current_text:
        return 1.0, "line-text-near-exact"

    text_similarity = _line_similarity(original_text, current_text)
    if original_text and current_text and text_similarity >= 0.82:
        return 0.92, "line-text-similar"

    if original_message and current_message and original_message == current_message:
        if original_text and current_text and text_similarity >= 0.55:
            return 0.84, "message-and-line-similar"
        if original_line and current_line and abs(current_line - original_line) <= 10:
            return 0.62, "message-and-line-window"

    original_fp = compute_issue_fingerprint(original_issue, original_content)
    current_fp = compute_issue_fingerprint(current_issue, current_content)
    if original_fp == current_fp:
        return 0.75, "context-fingerprint"

    return 0.0, "no-match"


def _match_issues_in_file(
    original_issues_with_content: Sequence[Tuple[Dict[str, Any], str]],
    current_issues: Sequence[Dict[str, Any]],
    current_content: str,
) -> List[Dict[str, Any]]:
    """
    Match original issues to current issues without reusing the same current
    issue multiple times.
    """
    used_current_indexes: set[int] = set()
    matches: List[Dict[str, Any]] = []

    for original_issue, original_content in original_issues_with_content:
        best_index = -1
        best_score = 0.0
        best_reason = "no-match"

        for index, current_issue in enumerate(current_issues):
            if index in used_current_indexes:
                continue
            score, reason = _score_issue_candidate(
                original_issue,
                original_content,
                current_issue,
                current_content,
            )
            if score > best_score:
                best_index = index
                best_score = score
                best_reason = reason

        if best_index >= 0 and best_score >= 0.60:
            used_current_indexes.add(best_index)
            matches.append(
                {
                    "original": original_issue,
                    "survived": True,
                    "current": current_issues[best_index],
                    "match_score": round(best_score, 3),
                    "match_reason": best_reason,
                }
            )
        else:
            matches.append(
                {
                    "original": original_issue,
                    "survived": False,
                    "current": None,
                    "match_score": 0.0,
                    "match_reason": "no-match",
                }
            )

    return matches


def find_issue_at_head(
    repo_dir: Path,
    original_issue: Dict[str, Any],
    original_file_path: str,
    original_content: str,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Compatibility wrapper used by a few ad-hoc scripts.
    """
    current_content, resolved_path = resolve_file_at_head(repo_dir, original_file_path)
    if not current_content:
        return False, None

    from src.filters import get_language_extension

    language = detect_language(resolved_path)
    file_ext = get_language_extension(language)
    quality_result = analyze_file_quality(
        current_content,
        language,
        file_ext,
        debug=True,
        source_path=resolved_path,
    )
    current_issues = quality_result.get("issues", []) or []

    if language == "python" and _normalize_rule_id(original_issue).startswith("B"):
        current_issues = _augment_python_issues_with_bandit(current_content, resolved_path, current_issues)

    matches = _match_issues_in_file([(original_issue, original_content)], current_issues, current_content)
    if not matches:
        return False, None
    match = matches[0]
    return match["survived"], match["current"]


def analyze_issue_survival(
    repo_dir: Path,
    commit_issues: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze survival of issues from AI commits.
    """
    if not commit_issues:
        return {
            "total_issues": 0,
            "surviving_issues": 0,
            "fixed_issues": 0,
            "survival_rate": 0.0,
            "by_severity": {},
            "by_rule": {},
            "issues": [],
        }

    from src.filters import get_language_extension

    results: List[Dict[str, Any]] = []
    surviving_count = 0
    by_severity: Dict[str, Dict[str, Any]] = {}
    by_rule: Dict[str, Dict[str, Any]] = {}

    grouped_by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for issue in commit_issues:
        grouped_by_file[issue.get("file_path", "")].append(issue)

    head_file_cache: Dict[Tuple[str, bool], Dict[str, Any]] = {}

    def _get_head_file_analysis(file_path: str, needs_bandit: bool) -> Dict[str, Any]:
        cache_key = (file_path, needs_bandit)
        if cache_key in head_file_cache:
            return head_file_cache[cache_key]

        current_content, resolved_path = resolve_file_at_head(repo_dir, file_path)
        if not current_content:
            head_file_cache[cache_key] = {
                "content": None,
                "issues": [],
                "resolved_path": file_path,
            }
            return head_file_cache[cache_key]

        language = detect_language(resolved_path)
        file_ext = get_language_extension(language)
        quality_result = analyze_file_quality(
            current_content,
            language,
            file_ext,
            debug=True,
            source_path=resolved_path,
        )
        current_issues = quality_result.get("issues", []) or []

        if needs_bandit and language == "python":
            current_issues = _augment_python_issues_with_bandit(current_content, resolved_path, current_issues)

        head_file_cache[cache_key] = {
            "content": current_content,
            "issues": current_issues,
            "resolved_path": resolved_path,
        }
        return head_file_cache[cache_key]

    for file_path, issues_in_file in grouped_by_file.items():
        if not file_path:
            continue

        original_entries: List[Tuple[Dict[str, Any], str]] = []
        needs_bandit = False

        for issue in issues_in_file:
            commit_sha = issue.get("commit_sha", "HEAD~1")
            original_content = issue.get("file_content_at_commit")
            if original_content is None:
                original_content = get_file_at_commit(repo_dir, commit_sha, file_path) or ""
            original_entries.append((issue, original_content))
            if detect_language(file_path) == "python" and _normalize_rule_id(issue).startswith("B"):
                needs_bandit = True

        head_analysis = _get_head_file_analysis(file_path, needs_bandit)
        current_content = head_analysis.get("content") or ""
        current_issues = head_analysis.get("issues") or []

        file_matches = _match_issues_in_file(original_entries, current_issues, current_content)
        for match in file_matches:
            match["resolved_path"] = head_analysis.get("resolved_path", file_path)
            results.append(match)

            if match["survived"]:
                surviving_count += 1

            issue = match["original"]
            severity = str(issue.get("severity", "UNKNOWN")).upper()
            by_severity.setdefault(severity, {"total": 0, "surviving": 0})
            by_severity[severity]["total"] += 1
            if match["survived"]:
                by_severity[severity]["surviving"] += 1

            rule_id = _normalize_rule_id(issue)
            by_rule.setdefault(rule_id, {"total": 0, "surviving": 0})
            by_rule[rule_id]["total"] += 1
            if match["survived"]:
                by_rule[rule_id]["surviving"] += 1

    total = len(commit_issues)
    survival_rate = surviving_count / total if total else 0.0

    for severity_data in by_severity.values():
        total_count = severity_data["total"]
        severity_data["rate"] = severity_data["surviving"] / total_count if total_count else 0.0

    for rule_data in by_rule.values():
        total_count = rule_data["total"]
        rule_data["rate"] = rule_data["surviving"] / total_count if total_count else 0.0

    return {
        "total_issues": total,
        "surviving_issues": surviving_count,
        "fixed_issues": total - surviving_count,
        "survival_rate": survival_rate,
        "by_severity": by_severity,
        "by_rule": by_rule,
        "issues": results,
    }


def get_issue_survival_summary(survival_data: Dict[str, Any]) -> str:
    """Generate a human-readable summary of issue survival analysis."""
    total = survival_data.get("total_issues", 0)
    surviving = survival_data.get("surviving_issues", 0)
    fixed = survival_data.get("fixed_issues", 0)
    rate = survival_data.get("survival_rate", 0.0)

    lines = [
        "=" * 50,
        "ISSUE SURVIVAL ANALYSIS",
        "=" * 50,
        f"Total AI-introduced issues:  {total}",
        f"Still exist at HEAD:         {surviving} ({rate * 100:.1f}%)",
        f"Fixed since introduction:    {fixed} ({(1 - rate) * 100:.1f}%)",
        "",
        "By Severity:",
    ]

    for severity, data in survival_data.get("by_severity", {}).items():
        total_count = data.get("total", 0)
        surviving_count = data.get("surviving", 0)
        severity_rate = data.get("rate", 0.0)
        lines.append(f"  {severity}: {surviving_count}/{total_count} surviving ({severity_rate * 100:.1f}%)")

    lines.append("")
    lines.append("Top Surviving Issue Types:")

    by_rule = survival_data.get("by_rule", {})
    sorted_rules = sorted(by_rule.items(), key=lambda item: item[1].get("surviving", 0), reverse=True)
    for rule_id, data in sorted_rules[:5]:
        surviving_count = data.get("surviving", 0)
        total_count = data.get("total", 0)
        rule_rate = data.get("rate", 0.0)
        lines.append(f"  {rule_id}: {surviving_count}/{total_count} ({rule_rate * 100:.1f}%)")

    lines.append("=" * 50)
    return "\n".join(lines)
