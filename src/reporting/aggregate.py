#!/usr/bin/env python3
"""
Aggregate cross-repo research statistics for the overview dashboard.

Scans all repos in the output directory and computes:
- RQ1: What issues does AI code introduce? (by type, severity, rule, tool)
- RQ2: How do different AI tools compare? (per-tool issue rates)
- RQ3: Do issues survive? (survival rates by severity, tool, rule)

Saves results to aggregate_summary.json for the overview dashboard.

Can be used as a module:
    from src.aggregate import aggregate_and_save
    aggregate_and_save("out")  # auto-detects if re-computation needed

Or as a CLI:
    python -m src.aggregate --out-dir out
    python -m src.aggregate --out-dir out --force
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config.blocked_rules import LOW_SIGNAL_RULES, filter_issues, is_issue_low_signal
from src.filters import is_noise_path

logger = logging.getLogger(__name__)

_REPO_META_CACHE: Optional[Dict[str, Dict]] = None
FOCUSED_TOOLS = {"copilot", "claude", "cursor", "gemini", "devin"}

FALSE_POSITIVE_PATTERN_META = {
    "embedded_env": {
        "label": "Embedded Environment / Installed Package Code",
        "description": "Paths under virtual environments or site-packages are installed dependencies, not repository-authored production code.",
        "category": "likely_false_positive",
    },
    "vendored_dependency": {
        "label": "Vendored / Third-Party Dependency Code",
        "description": "Vendored bundles and third-party libraries should not drive AI debt metrics for the host repository.",
        "category": "likely_false_positive",
    },
    "dev_tool_context": {
        "label": "Developer Tool / CLI Context Warning",
        "description": "Warnings like logging interpolation or unspecified encoding are common noise in scripts and CLI tooling.",
        "category": "likely_false_positive",
    },
}

DEV_TOOL_WARNING_RULES = {
    "logging-fstring-interpolation",
    "import-outside-toplevel",
    "unspecified-encoding",
}

def _record_sample(bucket: Dict[str, List[str]], key: str, path: str, limit: int = 5) -> None:
    samples = bucket[key]
    if path and path not in samples and len(samples) < limit:
        samples.append(path)


def _classify_false_positive_pattern(file_path: str, rule: str) -> Optional[str]:
    normalized = (file_path or "").replace("\\", "/").lower()
    if any(part in normalized for part in ("/site-packages/", "/dist-packages/", "/.venv/", "/venv/", "/env/", "/virtualenv/")):
        return "embedded_env"
    if any(part in normalized for part in ("/_vendor/", "/vendor/", "/third_party/", "/third-party/", "/external/", "/node_modules/")):
        return "vendored_dependency"
    if rule in DEV_TOOL_WARNING_RULES and re.search(r"(^|/)(scripts?|tools?|cli|bin)(/|$)", normalized):
        return "dev_tool_context"
    return None


def _load_repo_meta() -> Dict[str, Dict]:
    """
    Build a lookup dict {repo_full_name -> {stars, language, url}} from
    data/ai_repos.csv.  Result is cached so the file is read only once.
    """
    global _REPO_META_CACHE
    if _REPO_META_CACHE is not None:
        return _REPO_META_CACHE

    import csv

    candidates = [
        Path("data/ai_repos.csv"),
        Path(__file__).parent.parent.parent / "data" / "ai_repos.csv",
    ]
    csv_path = next((p for p in candidates if p.exists()), None)
    if csv_path is None:
        logger.warning("data/ai_repos.csv not found — repo metadata (stars etc.) will be absent")
        _REPO_META_CACHE = {}
        return _REPO_META_CACHE

    meta: Dict[str, Dict] = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row.get("repo_name", "")
                if name and name not in meta:
                    try:
                        stars = int(row.get("stars") or 0)
                    except ValueError:
                        stars = 0
                    meta[name] = {
                        "stars": stars,
                        "language": row.get("language") or "",
                        "url": row.get("url") or f"https://github.com/{name}",
                    }
        logger.info("Loaded repo metadata for %d repos from %s", len(meta), csv_path)
    except Exception as exc:
        logger.warning("Failed to load repo metadata: %s", exc)

    # Fallback: load from focused_repos.json for repos missing from CSV
    rerun_candidates = [
        Path("data/focused_repos.json"),
        Path(__file__).parent.parent.parent / "data" / "focused_repos.json",
    ]
    for rp in rerun_candidates:
        if not rp.exists():
            continue
        try:
            rerun_data = json.loads(rp.read_text())
            rerun_repos = rerun_data.get("repos", []) if isinstance(rerun_data, dict) else rerun_data
            added = 0
            for entry in rerun_repos:
                name = entry.get("repo", "")
                if name and name not in meta:
                    meta[name] = {
                        "stars": int(entry.get("stars") or 0),
                        "language": entry.get("language") or "",
                        "url": f"https://github.com/{name}",
                    }
                    added += 1
            if added:
                logger.info("Loaded %d additional repos from %s", added, rp)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", rp, exc)
        break

    _REPO_META_CACHE = meta
    return meta


def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _filter_file_issues(file_data: Dict[str, Any], issue_key: str) -> List[Dict[str, Any]]:
    file_path = file_data.get("file_path", "")
    context_key = "issue_filter_context_before" if issue_key == "issues_resolved" else "issue_filter_context_after"
    return filter_issues(
        file_data.get(issue_key, []) or [],
        file_path=file_path,
        context=file_data.get(context_key),
    )


def _survival_issue_key(
    commit_sha: str,
    file_path: str,
    issue: Dict[str, Any],
) -> Tuple[str, str, int, str, str, str]:
    line = issue.get("line", 0)
    try:
        line_num = int(line or 0)
    except (TypeError, ValueError):
        line_num = 0
    issue_type = str(issue.get("type") or issue.get("detected_by") or "")
    message = str(issue.get("message") or "")
    severity = str(issue.get("severity") or "")
    return (commit_sha, file_path, line_num, issue_type, message, severity)


def _build_survival_issue_lookup(debt_data: List[Dict[str, Any]]) -> Dict[Tuple[str, str, int, str, str, str], Dict[str, Any]]:
    lookup: Dict[Tuple[str, str, int, str, str, str], Dict[str, Any]] = {}
    for commit in debt_data:
        commit_sha = str(commit.get("commit_hash") or "")
        for file_data in commit.get("files", []) or []:
            file_path = str(file_data.get("file_path") or "")
            context = file_data.get("issue_filter_context_after")
            for issue in file_data.get("issues_added", []) or []:
                enriched_issue = dict(issue)
                if context and isinstance(context, dict):
                    enriched_issue.setdefault("filter_context", context)
                enriched_issue.setdefault("file_path", file_path)
                key = _survival_issue_key(commit_sha, file_path, issue)
                lookup.setdefault(key, enriched_issue)
    return lookup


def _hydrate_survival_original(
    original: Dict[str, Any],
    issue_lookup: Optional[Dict[Tuple[str, str, int, str, str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    hydrated = dict(original)
    if issue_lookup is None:
        return hydrated

    key = _survival_issue_key(
        str(original.get("commit_sha") or ""),
        str(original.get("file_path") or ""),
        original,
    )
    matched = issue_lookup.get(key)
    if not matched:
        return hydrated

    recovered_rule = matched.get("rule") or matched.get("symbol") or matched.get("rule_id")
    generic_rule_id = hydrated.get("rule_id") in {"", None, hydrated.get("type")}
    if generic_rule_id and recovered_rule:
        hydrated["rule_id"] = recovered_rule

    for field in ("rule", "symbol", "_is_low_severity", "filter_context", "detected_by", "category"):
        value = matched.get(field)
        if value is not None:
            hydrated[field] = value

    return hydrated


def _filter_survival_entries(
    surv_data: Dict[str, Any],
    issue_lookup: Optional[Dict[Tuple[str, str, int, str, str, str], Dict[str, Any]]] = None,
    noise_rules: Optional[Set[str]] = None,
) -> Optional[List[Dict[str, Any]]]:
    issues = surv_data.get("issues")
    if not isinstance(issues, list):
        return None

    noise = noise_rules or set()
    filtered_entries: List[Dict[str, Any]] = []
    for entry in issues:
        original = _hydrate_survival_original(entry.get("original") or {}, issue_lookup)
        filtered_original = filter_issues(
            [original],
            rule_key="rule_id",
            file_path=original.get("file_path", ""),
            context=original.get("filter_context"),
        )
        if not filtered_original:
            continue
        # Also filter noise/low-signal rules (same as actionable counts)
        rule = (
            filtered_original[0].get("rule_id")
            or filtered_original[0].get("symbol")
            or filtered_original[0].get("rule")
            or ""
        )
        if rule in noise:
            continue
        if is_issue_low_signal(filtered_original[0], file_path=original.get("file_path", "")):
            continue
        filtered_entry = dict(entry)
        filtered_entry["original"] = filtered_original[0]
        filtered_entries.append(filtered_entry)

    return filtered_entries


def _summarize_survival_entries(
    entries: List[Dict[str, Any]],
    issue_lookup: Optional[Dict[Tuple[str, str, int, str, str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    total = len(entries)
    surviving = sum(1 for entry in entries if entry.get("survived"))
    by_severity: Dict[str, Dict[str, Any]] = {}
    by_rule: Dict[str, Dict[str, Any]] = {}
    by_family: Dict[str, Dict[str, int]] = {}

    for entry in entries:
        original = _hydrate_survival_original(entry.get("original") or {}, issue_lookup)
        severity = str(original.get("severity", "UNKNOWN")).upper()
        rule = (
            original.get("rule_id")
            or original.get("rule")
            or original.get("symbol")
            or original.get("type")
            or "unknown"
        )
        survived = bool(entry.get("survived"))
        family = classify_issue_family(original)

        by_severity.setdefault(severity, {"total": 0, "surviving": 0})
        by_severity[severity]["total"] += 1
        if survived:
            by_severity[severity]["surviving"] += 1

        by_rule.setdefault(rule, {"total": 0, "surviving": 0})
        by_rule[rule]["total"] += 1
        if survived:
            by_rule[rule]["surviving"] += 1

        by_family.setdefault(family, {"total": 0, "surviving": 0})
        by_family[family]["total"] += 1
        if survived:
            by_family[family]["surviving"] += 1

    for bucket in by_severity.values():
        total_count = bucket["total"]
        bucket["rate"] = bucket["surviving"] / total_count if total_count else 0.0

    for bucket in by_rule.values():
        total_count = bucket["total"]
        bucket["rate"] = bucket["surviving"] / total_count if total_count else 0.0

    for bucket in by_family.values():
        total_count = bucket["total"]
        bucket["rate"] = bucket["surviving"] / total_count if total_count else 0.0

    return {
        "total_issues": total,
        "surviving_issues": surviving,
        "fixed_issues": total - surviving,
        "survival_rate": surviving / total if total else 0.0,
        "by_severity": by_severity,
        "by_rule": by_rule,
        "by_family": by_family,
    }


def _build_top_surviving_rules(
    surviving_counter: Counter,
    total_counter: Counter,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for rule, surviving in surviving_counter.most_common(limit):
        total = total_counter.get(rule, surviving)
        rows.append({
            "rule": rule,
            "description": BANDIT_RULE_NAMES.get(rule, ""),
            "surviving": surviving,
            "total": total,
            "rate": round(surviving / total, 3) if total > 0 else 0,
        })
    return rows


def normalize_severity(issue: dict) -> str:
    itype = (issue.get("type") or issue.get("detected_by") or "").lower()
    sev = (str(issue.get("severity") or "")).lower()
    if itype == "pylint":
        if sev in ("fatal", "error"):
            return "high"
        if sev == "warning":
            return "medium"
        return "low"
    if itype == "eslint":
        return "high" if sev == "error" else "medium"
    if sev in ("high", "error", "critical", "blocker", "fatal"):
        return "high"
    if sev in ("medium", "warning", "major"):
        return "medium"
    if sev in ("low", "info", "minor", "style", "convention", "refactor"):
        return "low"
    return "medium"


def is_security_issue(issue: dict) -> bool:
    cat = (issue.get("category") or "").lower()
    itype = (issue.get("type") or issue.get("detected_by") or "").lower()
    rule = issue.get("rule_id") or issue.get("symbol") or issue.get("rule") or ""
    if cat == "security" or itype in ("security", "bandit", "semgrep"):
        return True
    if rule.startswith("B") and rule[1:4].isdigit():
        return True
    return False


BUG_RULES = {
    # Pylint error-level rules that indicate actual runtime bugs
    "undefined-variable",        # name used without definition (some FPs from wildcard imports)
    "possibly-used-before-assignment",  # conditional assignment gaps
    "not-callable",              # calling non-callable object
    "not-an-iterable",           # iterating non-iterable
    "missing-kwoa",              # missing mandatory keyword argument
    "function-redefined",        # function silently overwritten
    "access-member-before-definition",  # accessing member before __init__
    "assignment-from-no-return", # assigning result of void function
    "unsubscriptable-object",    # subscripting non-subscriptable
    "unreachable",               # unreachable code
    # NOTE: used-before-assignment excluded (66% FP from TYPE_CHECKING guards)
    # NOTE: no-self-argument excluded (FPs from metaclass/descriptor patterns)
    # NOTE: no-value-for-parameter excluded (FPs from classmethod 'cls')
    # ESLint rules that indicate actual runtime bugs
    # NOTE: no-undef excluded (too many FPs from missing globals)
    # NOTE: no-use-before-define excluded (valid JS function hoisting flagged as error)
    "no-unreachable", "no-redeclare", "no-dupe-keys", "no-dupe-args",
    "no-dupe-else-if", "no-func-assign", "no-import-assign", "no-self-assign",
    "no-self-compare", "use-isnan", "no-setter-return", "getter-return",
    "no-constant-binary-expression", "no-constructor-return",
    "valid-typeof", "no-loss-of-precision",
}

BANDIT_RULE_NAMES = {
    "B101": "Assert Used", "B102": "exec() Used", "B103": "Permissive File Permissions",
    "B104": "Binding to All Interfaces", "B105": "Hardcoded Password (arg)",
    "B106": "Hardcoded Password (func)", "B107": "Hardcoded Password (default)",
    "B108": "Insecure Temp File", "B110": "Try-Except-Pass", "B112": "Try-Except-Continue",
    "B113": "Requests Without Timeout", "B201": "Flask Debug Mode",
    "B202": "Unsafe tarfile.extractall", "B301": "Pickle Deserialization",
    "B307": "Unsafe eval-like Function", "B310": "Unsafe URL Open",
    "B311": "Insecure Random Generator", "B314": "Unsafe XML Parsing",
    "B324": "Weak Hash (MD5/SHA1)", "B403": "Pickle Import", "B404": "Subprocess Import",
    "B501": "SSL verify=False", "B506": "Unsafe YAML Load",
    "B602": "Subprocess with shell=True", "B603": "Subprocess Without Shell Check",
    "B604": "Function with shell=True", "B605": "Process with Shell",
    "B607": "Partial Executable Path", "B608": "SQL Injection via String Format",
    "B614": "Unsafe PyTorch Load", "B615": "Unsafe HuggingFace Hub Download",
    "B701": "Jinja2 Autoescape Disabled",
}

def classify_issue_family(issue: dict) -> str:
    """Classify into security / bug / code_smell based on rule semantics."""
    if is_security_issue(issue):
        return "security"
    rule = issue.get("rule_id") or issue.get("symbol") or issue.get("rule") or ""
    cat = (issue.get("category") or "").lower()
    if rule in BUG_RULES or cat in {"bug", "reliability", "correctness"}:
        return "bug"
    return "code_smell"


def language_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript"}.get(ext, "other")


def is_tainted_commit(commit: dict) -> bool:
    """
    Detect commits whose debt metrics are corrupted by the shallow-clone
    parent-resolution fallback.

    When `get_commit_parent()` cannot resolve the parent SHA (e.g. because
    the repo was cloned with --depth N and this commit sits at the boundary),
    `list_changed_files_with_status` falls back to `git diff-tree --root`,
    which lists the ENTIRE repository tree as "Added".  The result is that
    pre-existing issues in hundreds of unrelated files are attributed to a
    single commit, massively inflating its issue count.

    Fingerprint of a tainted commit:
      • files_total reported by analysis_counters is very large (> 200), AND
      • every file in the `files` list has status "A" (Added).

    A true root commit that genuinely adds many files would satisfy the
    second condition but almost never the first in real-world AI-authored
    code (it would require a single commit to introduce > 200 analysable
    Python/JS/TS files, which is exceedingly rare).
    """
    counters = commit.get("analysis_counters", {})
    files_total = counters.get("files_total", 0)
    if files_total <= 200:
        return False
    files = commit.get("files", [])
    if not files:
        return False
    return all(f.get("status") == "A" for f in files)


def aggregate(out_dir: str) -> Dict[str, Any]:
    """Walk all repo output directories and compute aggregate statistics."""
    start = time.time()
    out_path = Path(out_dir)

    # Load repo metadata (stars, language, url) from CSV — fast lookup
    repo_meta = _load_repo_meta()

    # Load commit-level metadata (author_role, date) from data/commits/
    commit_roles: Dict[str, str] = {}
    commit_dates: Dict[str, str] = {}  # sha[:12] -> "YYYY-MM"
    commits_dir_candidates = [
        Path("data/commits"),
        Path(__file__).parent.parent.parent / "data" / "commits",
    ]
    commits_dir = next((p for p in commits_dir_candidates if p.is_dir()), None)
    if commits_dir:
        for cf in commits_dir.iterdir():
            if not cf.name.endswith("_commits.json"):
                continue
            try:
                cd = load_json(str(cf))
                if not isinstance(cd, dict):
                    continue
                for ac in cd.get("ai_commits", []):
                    sha = ac.get("sha", "")
                    role = ac.get("author_role", "")
                    date = ac.get("date", "")
                    if sha and role:
                        commit_roles[sha[:12]] = role
                    if sha and date and len(date) >= 7 and date[:4].isdigit():
                        commit_dates[sha[:12]] = date[:7]
            except Exception:
                pass
        logger.info("Loaded author_role for %d commits from %s", len(commit_roles), commits_dir)

    # Noise rule sets for actionable filtering
    STYLE_RULE_SET = {"line-too-long", "trailing-whitespace", "missing-final-newline",
                      "bad-indentation", "wrong-import-order", "wrong-import-position",
                      "superfluous-parens", "trailing-newlines"}
    CONVENTION_RULE_SET = {"missing-function-docstring", "missing-class-docstring",
                           "missing-module-docstring", "invalid-name", "disallowed-name", "empty-docstring"}
    LIKELY_FP_RULE_SET = {
        "no-member",             # dynamic attributes, metaclass
        "not-an-iterable",       # Pydantic Field()
        "not-callable",          # dynamic dispatch
        "unexpected-keyword-arg",  # ORM/metaclass constructors
        "no-undef",              # missing ESLint globals without project context
        "used-before-assignment", # 66% FP from TYPE_CHECKING guards
        "no-value-for-parameter", # FP from classmethod 'cls'
        "no-self-argument",      # metaclass/descriptor patterns
    }
    ALL_NOISE_RULES = STYLE_RULE_SET | CONVENTION_RULE_SET | LIKELY_FP_RULE_SET | LOW_SIGNAL_RULES

    # Actionable issue tracking
    actionable_introduced = 0
    actionable_fixed = 0
    actionable_sev: Counter = Counter()
    actionable_fixed_sev: Counter = Counter()
    actionable_type: Counter = Counter()
    actionable_lang: Counter = Counter()
    repos_with_code = 0

    # ── Collection ──
    all_repos: List[Dict] = []
    total_commits = 0
    total_issues_introduced = 0
    total_issues_fixed = 0

    # By tool
    tool_commits: Counter = Counter()
    tool_issues: Counter = Counter()
    tool_security: Counter = Counter()
    tool_issues_list: Dict[str, List[int]] = defaultdict(list)  # per-commit counts
    tool_high_issues: Counter = Counter()  # HIGH severity per tool
    tool_repos: Counter = Counter()  # dominant-tool repo count per tool

    # By author role
    role_commits: Counter = Counter()   # commits per role
    role_issues: Counter = Counter()    # issues per role
    role_fixed: Counter = Counter()     # fixed issues per role
    role_high: Counter = Counter()      # high-severity issues per role
    role_security: Counter = Counter()  # security issues per role
    focused_role_commits: Counter = Counter()
    focused_role_issues: Counter = Counter()
    focused_role_fixed: Counter = Counter()
    focused_role_high: Counter = Counter()
    focused_role_security: Counter = Counter()
    # Per-tool role breakdown: tool -> role -> count
    tool_role_commits: Dict[str, Counter] = defaultdict(Counter)
    tool_role_issues: Dict[str, Counter] = defaultdict(Counter)
    tool_role_issues_list: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    focused_tool_role_commits: Dict[str, Counter] = defaultdict(Counter)
    focused_tool_role_issues: Dict[str, Counter] = defaultdict(Counter)
    focused_tool_role_issues_list: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    # Normalized metrics: files analyzed, zero-issue commits
    total_files_analyzed = 0
    role_files: Counter = Counter()          # role -> total files analyzed
    role_zero_commits: Counter = Counter()   # role -> commits with 0 issues
    tool_files: Counter = Counter()          # tool -> total files analyzed
    tool_role_files: Dict[str, Counter] = defaultdict(Counter)     # tool -> role -> files
    tool_role_zero: Dict[str, Counter] = defaultdict(Counter)      # tool -> role -> zero-issue commits
    tool_zero_commits: Counter = Counter()   # tool -> zero-issue commits
    focused_role_files: Counter = Counter()
    focused_role_zero_commits: Counter = Counter()
    focused_tool_role_files: Dict[str, Counter] = defaultdict(Counter)
    focused_tool_role_zero: Dict[str, Counter] = defaultdict(Counter)

    # Per-role detailed breakdowns
    role_sev_counts: Dict[str, Counter] = defaultdict(Counter)        # role -> {sev: count}
    role_type_counts: Dict[str, Counter] = defaultdict(Counter)       # role -> {type: count}
    role_lang_counts: Dict[str, Counter] = defaultdict(Counter)       # role -> {lang: count}
    role_rule_counts: Dict[str, Counter] = defaultdict(Counter)       # role -> {rule: count}
    role_rule_sev: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    role_monthly_commits: Dict[str, Counter] = defaultdict(Counter)   # role -> {month: count}
    role_monthly_issues: Dict[str, Counter] = defaultdict(Counter)    # role -> {month: count}
    role_monthly_high: Dict[str, Counter] = defaultdict(Counter)      # role -> {month: count}
    focused_role_sev_counts: Dict[str, Counter] = defaultdict(Counter)
    focused_role_type_counts: Dict[str, Counter] = defaultdict(Counter)
    focused_role_lang_counts: Dict[str, Counter] = defaultdict(Counter)
    focused_role_rule_counts: Dict[str, Counter] = defaultdict(Counter)
    focused_role_rule_sev: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    focused_role_monthly_commits: Dict[str, Counter] = defaultdict(Counter)
    focused_role_monthly_issues: Dict[str, Counter] = defaultdict(Counter)
    focused_role_monthly_high: Dict[str, Counter] = defaultdict(Counter)

    # By severity
    sev_counts: Counter = Counter()

    # By type/analyzer
    type_counts: Counter = Counter()
    family_counts: Counter = Counter()

    # By rule
    rule_counts: Counter = Counter()
    rule_sev_counts: Dict[str, Counter] = defaultdict(Counter)  # rule -> {high: N, medium: N, low: N}

    # False-positive / low-signal pattern tracking
    false_positive_counts: Counter = Counter()
    false_positive_rule_counts: Dict[str, Counter] = defaultdict(Counter)
    false_positive_samples: Dict[str, List[str]] = defaultdict(list)
    low_signal_rule_counts: Counter = Counter()
    low_signal_samples: Dict[str, List[str]] = defaultdict(list)

    # By language
    lang_counts: Counter = Counter()

    # Time-series: monthly buckets (YYYY-MM -> counts)
    monthly_commits: Counter = Counter()
    monthly_issues: Counter = Counter()
    monthly_high: Counter = Counter()
    monthly_by_tool: Dict[str, Counter] = defaultdict(Counter)  # tool -> {month: commit_count}
    monthly_issues_by_tool: Dict[str, Counter] = defaultdict(Counter)  # tool -> {month: issue_count}
    monthly_high_by_tool: Dict[str, Counter] = defaultdict(Counter)  # tool -> {month: high_count}

    # Issue survival
    survival_total = 0
    survival_surviving = 0
    survival_by_sev: Dict[str, Dict[str, int]] = {}
    survival_by_tool: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "surviving": 0})
    survival_by_rule: Counter = Counter()
    survival_by_rule_total: Counter = Counter()
    focused_survival_total = 0
    focused_survival_surviving = 0
    survival_by_family: Dict[str, Dict[str, int]] = {}
    focused_survival_by_sev: Dict[str, Dict[str, int]] = {}
    focused_survival_by_family: Dict[str, Dict[str, int]] = {}
    focused_survival_by_rule: Counter = Counter()
    focused_survival_by_rule_total: Counter = Counter()

    # Survival by introduction month (for time-based survival analysis)
    # month -> {"total": N, "surviving": N}
    survival_by_month: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "surviving": 0})
    focused_survival_by_month: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "surviving": 0})
    # (month, family) -> {"total": N, "surviving": N}
    focused_survival_by_month_family: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"total": 0, "surviving": 0})
    )

    # Line/semantic survival
    line_survival_rates: List[float] = []
    semantic_survival_rates: List[float] = []
    per_repo_survival: List[Dict] = []
    focused_line_survival_rates: List[float] = []
    focused_semantic_survival_rates: List[float] = []
    focused_per_repo_survival: List[Dict] = []

    # File lifecycle
    files_survived = 0
    files_modified = 0
    files_deleted = 0
    files_fixed = 0
    files_refactored = 0
    focused_files_survived = 0
    focused_files_modified = 0
    focused_files_deleted = 0
    focused_files_fixed = 0
    focused_files_refactored = 0

    # Per-repo summary for distribution
    repo_issue_rates: List[float] = []

    # High-debt commits (track both total and high-severity)
    high_debt_commits: List[Dict] = []

    # Scan all repo directories
    repo_dirs = sorted([d for d in out_path.iterdir() if d.is_dir() and (d / "debt_metrics.json").exists()])
    logger.info("Found %d repo directories with results", len(repo_dirs))

    for repo_dir in repo_dirs:
        repo_name = repo_dir.name.replace("_", "/", 1)

        # Load debt metrics
        debt_data = load_json(str(repo_dir / "debt_metrics.json"))
        if not isinstance(debt_data, list):
            continue
        survival_issue_lookup = _build_survival_issue_lookup(debt_data)

        repo_commits = len(debt_data)
        repo_introduced = 0
        repo_fixed = 0
        repo_high = 0
        repo_security = 0
        repo_tool_counts: Counter = Counter()
        repo_introduced_sole = 0
        repo_introduced_co = 0
        repo_fixed_sole = 0
        repo_fixed_co = 0
        commit_tool_lookup: Dict[str, str] = {}

        # Try to load debug files for timestamps
        debug_dir = repo_dir / "debug"
        commit_timestamps: Dict[str, str] = {}
        if debug_dir.exists():
            for df in debug_dir.iterdir():
                if df.suffix == ".json":
                    try:
                        dd = load_json(str(df))
                        if dd and dd.get("commit_hash") and dd.get("timestamp"):
                            sha12 = dd["commit_hash"][:12]
                            ts = dd["timestamp"]
                            commit_timestamps[sha12] = ts
                            # Backfill commit_dates for SHAs missing from the
                            # data/commits/ manifest, so the focused loop's
                            # cohort table sees every analysed commit, not just
                            # those originally listed in the manifest.
                            if (
                                sha12 not in commit_dates
                                and len(ts) >= 7
                                and ts[:4].isdigit()
                            ):
                                commit_dates[sha12] = ts[:7]
                    except Exception:
                        pass

        for commit in debt_data:
            if is_tainted_commit(commit):
                logger.warning(
                    "Excluding tainted commit %s from %s "
                    "(shallow-clone fallback inflated %d files as Added)",
                    (commit.get("commit_hash") or "")[:12],
                    repo_name,
                    commit.get("analysis_counters", {}).get("files_total", 0),
                )
                continue

            commit_hash = str(commit.get("commit_hash") or "")
            tool = commit.get("ai_tool") or "unknown"
            focused_tool = tool in FOCUSED_TOOLS
            sha = commit_hash[:12]
            role = commit.get("author_role") or commit_roles.get(sha, "") or "unknown"
            if commit_hash:
                commit_tool_lookup[commit_hash] = tool
            if sha:
                commit_tool_lookup[sha] = tool
            tool_commits[tool] += 1
            total_commits += 1

            # Extract month from timestamp for time-series
            ts = commit_timestamps.get(sha, "")
            month = ""
            if ts and len(ts) >= 7 and ts[:4].isdigit():
                month = ts[:7]  # "YYYY-MM"
            if month:
                monthly_commits[month] += 1
                monthly_by_tool[tool][month] += 1
                role_monthly_commits[role][month] += 1

            commit_issues = 0
            commit_fixed = 0
            commit_security = 0
            commit_high = 0

            for f in commit.get("files", []):
                # Skip noise paths (vendored deps, site-packages, etc.)
                if is_noise_path(f.get("file_path", "")):
                    continue
                added_issues = _filter_file_issues(f, "issues_added")
                resolved_issues = _filter_file_issues(f, "issues_resolved")

                for issue in added_issues:
                    sev_norm = normalize_severity(issue)
                    itype = (issue.get("type") or issue.get("detected_by") or "unknown").lower()
                    rule = issue.get("symbol") or issue.get("rule") or issue.get("rule_id") or "unknown"
                    file_path = f.get("file_path") or ""
                    lang = language_from_path(file_path)
                    is_sec = is_security_issue(issue)
                    issue_is_low_signal = is_issue_low_signal(issue, file_path=file_path)

                    total_issues_introduced += 1
                    repo_introduced += 1
                    commit_issues += 1
                    sev_counts[sev_norm] += 1
                    type_counts[itype] += 1
                    lang_counts[lang] += 1
                    tool_issues[tool] += 1
                    # Per-role issue breakdowns
                    role_sev_counts[role][sev_norm] += 1
                    role_type_counts[role][itype] += 1
                    role_lang_counts[role][lang] += 1
                    if focused_tool:
                        focused_role_sev_counts[role][sev_norm] += 1
                        focused_role_type_counts[role][itype] += 1
                        focused_role_lang_counts[role][lang] += 1

                    fp_pattern = _classify_false_positive_pattern(file_path, rule)
                    if fp_pattern:
                        false_positive_counts[fp_pattern] += 1
                        false_positive_rule_counts[fp_pattern][rule] += 1
                        _record_sample(false_positive_samples, fp_pattern, file_path)
                    elif sev_norm == "low" or issue_is_low_signal:
                        low_signal_rule_counts[rule] += 1
                        _record_sample(low_signal_samples, rule, file_path)

                    if sev_norm == "high":
                        commit_high += 1
                        tool_high_issues[tool] += 1
                    if is_sec:
                        tool_security[tool] += 1
                        commit_security += 1
                    # Actionable = not noise
                    if rule not in ALL_NOISE_RULES and not fp_pattern and not issue_is_low_signal:
                        actionable_introduced += 1
                        actionable_sev[sev_norm] += 1
                        actionable_type[itype] += 1
                        actionable_lang[lang] += 1
                        family_counts[classify_issue_family(issue)] += 1
                        rule_counts[rule] += 1
                        rule_sev_counts[rule][sev_norm] += 1
                        role_rule_counts[role][rule] += 1
                        role_rule_sev[role][rule][sev_norm] += 1
                        if focused_tool:
                            focused_role_rule_counts[role][rule] += 1
                            focused_role_rule_sev[role][rule][sev_norm] += 1

                for issue in resolved_issues:
                    total_issues_fixed += 1
                    repo_fixed += 1
                    commit_fixed += 1
                    fixed_rule = issue.get("symbol") or issue.get("rule") or issue.get("rule_id") or ""
                    if fixed_rule not in ALL_NOISE_RULES and not is_issue_low_signal(issue, file_path=f.get("file_path") or ""):
                        actionable_fixed += 1
                        actionable_fixed_sev[normalize_severity(issue)] += 1

            tool_issues_list[tool].append(commit_issues)
            repo_high += commit_high
            repo_security += commit_security
            repo_tool_counts[tool] += 1

            # Files analyzed for normalized metrics
            n_files = commit.get("code_files_analyzed") or len(commit.get("files", []))
            total_files_analyzed += n_files
            tool_files[tool] += n_files
            role_files[role] += n_files
            tool_role_files[tool][role] += n_files
            if focused_tool:
                focused_role_files[role] += n_files
                focused_tool_role_files[tool][role] += n_files

            # Zero-issue commit tracking
            if commit_issues == 0:
                role_zero_commits[role] += 1
                tool_zero_commits[tool] += 1
                tool_role_zero[tool][role] += 1
                if focused_tool:
                    focused_role_zero_commits[role] += 1
                    focused_tool_role_zero[tool][role] += 1

            # Author role tracking
            role_commits[role] += 1
            role_issues[role] += commit_issues
            role_fixed[role] += commit_fixed
            role_high[role] += commit_high
            role_security[role] += commit_security
            tool_role_commits[tool][role] += 1
            tool_role_issues[tool][role] += commit_issues
            tool_role_issues_list[tool][role].append(commit_issues)
            if focused_tool:
                focused_role_commits[role] += 1
                focused_role_issues[role] += commit_issues
                focused_role_fixed[role] += commit_fixed
                focused_role_high[role] += commit_high
                focused_role_security[role] += commit_security
                focused_tool_role_commits[tool][role] += 1
                focused_tool_role_issues[tool][role] += commit_issues
                focused_tool_role_issues_list[tool][role].append(commit_issues)
            if role == "sole_author":
                repo_introduced_sole += commit_issues
                repo_fixed_sole += commit_fixed
            elif role == "coauthor":
                repo_introduced_co += commit_issues
                repo_fixed_co += commit_fixed

            if month:
                monthly_issues[month] += commit_issues
                monthly_high[month] += commit_high
                monthly_issues_by_tool[tool][month] += commit_issues
                monthly_high_by_tool[tool][month] += commit_high
                role_monthly_issues[role][month] += commit_issues
                role_monthly_high[role][month] += commit_high
                if focused_tool:
                    focused_role_monthly_commits[role][month] += 1
                    focused_role_monthly_issues[role][month] += commit_issues
                    focused_role_monthly_high[role][month] += commit_high

            # Track high-debt commits (store severity counts for better sorting)
            if commit_issues >= 5:
                high_debt_commits.append({
                    "repo": commit.get("repo") or repo_name,
                    "commit": sha,
                    "tool": tool,
                    "author_role": role,
                    "issues": commit_issues,
                    "high": commit_high,
                    "security": commit_security,
                    "month": month,
                })

        # Track repos with code
        repo_has_code = any(
            (c.get("code_files_analyzed") or len(c.get("files", []))) > 0
            for c in debt_data
            if not is_tainted_commit(c)
        )
        if repo_has_code:
            repos_with_code += 1

        # Per-repo rate
        if repo_commits > 0:
            repo_issue_rates.append(repo_introduced / repo_commits)

        repo_tool = repo_tool_counts.most_common(1)[0][0] if repo_tool_counts else "unknown"
        meta = repo_meta.get(repo_name, {})
        all_repos.append({
            "name": repo_name,
            "has_code": repo_has_code,
            "commits": repo_commits,
            "issues_introduced": repo_introduced,
            "issues_fixed": repo_fixed,
            "issues_high": repo_high,
            "issues_security": repo_security,
            "issues_per_commit": round(repo_introduced / repo_commits, 2) if repo_commits > 0 else 0,
            "tool": repo_tool,
            "stars": meta.get("stars", 0),
            "language": meta.get("language", ""),
            "github_url": meta.get("url", f"https://github.com/{repo_name}"),
            # Author role breakdown
            "issues_sole_author": repo_introduced_sole,
            "issues_coauthor": repo_introduced_co,
            "fixed_sole_author": repo_fixed_sole,
            "fixed_coauthor": repo_fixed_co,
            "pct_sole": round(100 * repo_introduced_sole / max(1, repo_introduced), 1),
        })
        tool_repos[repo_tool] += 1

        # Load issue survival
        surv_data = load_json(str(repo_dir / "issue_survival.json"))
        if isinstance(surv_data, dict) and surv_data.get("total_issues", 0) > 0:
            filtered_survival_entries = _filter_survival_entries(surv_data, survival_issue_lookup, noise_rules=ALL_NOISE_RULES)
            filtered_survival = (
                _summarize_survival_entries(filtered_survival_entries, survival_issue_lookup)
                if filtered_survival_entries is not None
                else surv_data
            )
            focused_filtered_survival = None
            if filtered_survival_entries is not None:
                focused_survival_entries = []
                for entry in filtered_survival_entries:
                    original = _hydrate_survival_original(entry.get("original") or {}, survival_issue_lookup)
                    commit_sha = str(original.get("commit_sha") or original.get("commit_hash") or "")
                    entry_tool = commit_tool_lookup.get(commit_sha) or commit_tool_lookup.get(commit_sha[:12], "unknown")
                    if entry_tool in FOCUSED_TOOLS:
                        focused_entry = dict(entry)
                        focused_entry["original"] = original
                        focused_survival_entries.append(focused_entry)
                focused_filtered_survival = _summarize_survival_entries(focused_survival_entries, survival_issue_lookup)

            # Track survival by introduction month
            if filtered_survival_entries is not None:
                for entry in filtered_survival_entries:
                    orig = entry.get("original") or {}
                    sha = str(orig.get("commit_sha") or orig.get("commit_hash") or "")
                    month = commit_dates.get(sha[:12], "")
                    if not month or len(month) < 7 or not month[:4].isdigit():
                        continue
                    survived = bool(entry.get("survived"))
                    survival_by_month[month]["total"] += 1
                    if survived:
                        survival_by_month[month]["surviving"] += 1

            st = filtered_survival.get("total_issues", 0)
            ss = filtered_survival.get("surviving_issues", 0)
            survival_total += st
            survival_surviving += ss

            for sev, data in filtered_survival.get("by_severity", {}).items():
                if sev not in survival_by_sev:
                    survival_by_sev[sev] = {"total": 0, "surviving": 0}
                survival_by_sev[sev]["total"] += data.get("total", 0)
                survival_by_sev[sev]["surviving"] += data.get("surviving", 0)

            for fam, data in filtered_survival.get("by_family", {}).items():
                if fam not in survival_by_family:
                    survival_by_family[fam] = {"total": 0, "surviving": 0}
                survival_by_family[fam]["total"] += data.get("total", 0)
                survival_by_family[fam]["surviving"] += data.get("surviving", 0)

            for rule, data in filtered_survival.get("by_rule", {}).items():
                survival_by_rule[rule] += data.get("surviving", 0)
                survival_by_rule_total[rule] += data.get("total", 0)

            # Attribute survival to repo's dominant tool
            repo_tool = repo_tool_counts.most_common(1)[0][0] if repo_tool_counts else "unknown"
            survival_by_tool[repo_tool]["total"] += st
            survival_by_tool[repo_tool]["surviving"] += ss

            per_repo_survival.append({
                "repo": repo_name,
                "total": st,
                "surviving": ss,
                "rate": ss / st if st > 0 else 0,
            })

            fst = (focused_filtered_survival or {}).get("total_issues", 0)
            fss = (focused_filtered_survival or {}).get("surviving_issues", 0)
            # Track focused survival by month
            if fst > 0 and focused_survival_entries:
                for entry in focused_survival_entries:
                    orig = entry.get("original") or {}
                    sha = str(orig.get("commit_sha") or orig.get("commit_hash") or "")
                    month = commit_dates.get(sha[:12], "")
                    if not month or len(month) < 7 or not month[:4].isdigit():
                        continue
                    survived = bool(entry.get("survived"))
                    focused_survival_by_month[month]["total"] += 1
                    if survived:
                        focused_survival_by_month[month]["surviving"] += 1
                    family = classify_issue_family(orig)
                    focused_survival_by_month_family[month][family]["total"] += 1
                    if survived:
                        focused_survival_by_month_family[month][family]["surviving"] += 1

            if fst > 0:
                focused_survival_total += fst
                focused_survival_surviving += fss
                for sev, data in (focused_filtered_survival or {}).get("by_severity", {}).items():
                    if sev not in focused_survival_by_sev:
                        focused_survival_by_sev[sev] = {"total": 0, "surviving": 0}
                    focused_survival_by_sev[sev]["total"] += data.get("total", 0)
                    focused_survival_by_sev[sev]["surviving"] += data.get("surviving", 0)
                for fam, data in (focused_filtered_survival or {}).get("by_family", {}).items():
                    if fam not in focused_survival_by_family:
                        focused_survival_by_family[fam] = {"total": 0, "surviving": 0}
                    focused_survival_by_family[fam]["total"] += data.get("total", 0)
                    focused_survival_by_family[fam]["surviving"] += data.get("surviving", 0)
                for rule, data in (focused_filtered_survival or {}).get("by_rule", {}).items():
                    focused_survival_by_rule[rule] += data.get("surviving", 0)
                    focused_survival_by_rule_total[rule] += data.get("total", 0)
                focused_per_repo_survival.append({
                    "repo": repo_name,
                    "total": fst,
                    "surviving": fss,
                    "rate": fss / fst if fst > 0 else 0,
                })

        # Load destiny (line survival)
        dest_data = load_json(str(repo_dir / "destiny_metrics.json"))
        if isinstance(dest_data, list):
            for d in dest_data:
                destiny_commit = str(d.get("commit") or "")
                destiny_tool = commit_tool_lookup.get(destiny_commit) or commit_tool_lookup.get(destiny_commit[:12], "unknown")
                if d.get("total_lines_added", 0) > 0:
                    line_survival_rates.append(d.get("survival_rate", 0))
                    if destiny_tool in FOCUSED_TOOLS:
                        focused_line_survival_rates.append(d.get("survival_rate", 0))
                if d.get("semantic_units_original", 0) > 0:
                    semantic_survival_rates.append(d.get("semantic_survival_rate", 0))
                    if destiny_tool in FOCUSED_TOOLS:
                        focused_semantic_survival_rates.append(d.get("semantic_survival_rate", 0))

        # Load lifecycle
        life_data = load_json(str(repo_dir / "lifecycle_metrics.json"))
        if isinstance(life_data, list):
            for commit in life_data:
                life_commit_hash = str(commit.get("commit_hash") or "")[:12]
                life_tool = str(commit.get("ai_tool") or commit_tool_lookup.get(life_commit_hash) or "unknown")
                focused_life_tool = life_tool in FOCUSED_TOOLS
                for f in commit.get("files", []):
                    status = f.get("status", "")
                    if status == "SURVIVED":
                        files_survived += 1
                    elif status == "MODIFIED":
                        files_modified += 1
                    elif status == "DELETED":
                        files_deleted += 1
                    if f.get("was_fixed"):
                        files_fixed += 1
                    if f.get("was_refactored"):
                        files_refactored += 1
                    if focused_life_tool:
                        if status == "SURVIVED":
                            focused_files_survived += 1
                        elif status == "MODIFIED":
                            focused_files_modified += 1
                        elif status == "DELETED":
                            focused_files_deleted += 1
                        if f.get("was_fixed"):
                            focused_files_fixed += 1
                        if f.get("was_refactored"):
                            focused_files_refactored += 1

    # ── Compute aggregates ──

    def _stats(values):
        if not values:
            return {"mean": 0, "median": 0, "p25": 0, "p75": 0, "min": 0, "max": 0, "count": 0}
        s = sorted(values)
        n = len(s)
        return {
            "mean": round(sum(s) / n, 4),
            "median": round(s[n // 2], 4),
            "p25": round(s[n // 4], 4),
            "p75": round(s[3 * n // 4], 4),
            "min": round(s[0], 4),
            "max": round(s[-1], 4),
            "count": n,
        }

    def _per_tool_stats():
        result = {}
        for tool in sorted(tool_commits.keys()):
            tc = tool_commits[tool]
            ti = tool_issues[tool]
            ts = tool_security[tool]
            th = tool_high_issues[tool]
            per_commit = tool_issues_list.get(tool, [])

            # Role breakdown per tool
            sole_commits = tool_role_commits[tool].get("sole_author", 0)
            co_commits = tool_role_commits[tool].get("coauthor", 0)
            sole_issues = tool_role_issues[tool].get("sole_author", 0)
            co_issues = tool_role_issues[tool].get("coauthor", 0)
            sole_list = tool_role_issues_list[tool].get("sole_author", [])
            co_list = tool_role_issues_list[tool].get("coauthor", [])

            tf = tool_files[tool]
            tz = tool_zero_commits[tool]
            sole_files_t = tool_role_files[tool].get("sole_author", 0)
            co_files_t = tool_role_files[tool].get("coauthor", 0)

            result[tool] = {
                "commits": tc,
                "issues_total": ti,
                "issues_high": th,
                "issues_security": ts,
                "issues_per_commit_mean": round(ti / tc, 2) if tc > 0 else 0,
                "issues_per_commit_median": round(sorted(per_commit)[len(per_commit) // 2], 2) if per_commit else 0,
                "high_pct": round(th / ti * 100, 1) if ti > 0 else 0,
                "security_pct": round(ts / ti * 100, 1) if ti > 0 else 0,
                # Normalized metrics
                "files_analyzed": tf,
                "files_per_commit": round(tf / tc, 2) if tc > 0 else 0,
                "issues_per_file": round(ti / tf, 2) if tf > 0 else 0,
                "zero_issue_pct": round(100 * tz / tc, 1) if tc > 0 else 0,
                "zero_issue_commits": tz,
                "repos": tool_repos.get(tool, 0),
                # Role breakdown
                "sole_author_commits": sole_commits,
                "coauthor_commits": co_commits,
                "sole_author_issues": sole_issues,
                "coauthor_issues": co_issues,
                "sole_issues_per_commit": round(sole_issues / sole_commits, 2) if sole_commits > 0 else 0,
                "co_issues_per_commit": round(co_issues / co_commits, 2) if co_commits > 0 else 0,
                "sole_issues_per_file": round(sole_issues / sole_files_t, 2) if sole_files_t > 0 else 0,
                "co_issues_per_file": round(co_issues / co_files_t, 2) if co_files_t > 0 else 0,
                "sole_files_per_commit": round(sole_files_t / sole_commits, 2) if sole_commits > 0 else 0,
                "co_files_per_commit": round(co_files_t / co_commits, 2) if co_commits > 0 else 0,
                "sole_issues_per_commit_median": round(sorted(sole_list)[len(sole_list) // 2], 2) if sole_list else 0,
                "co_issues_per_commit_median": round(sorted(co_list)[len(co_list) // 2], 2) if co_list else 0,
                "pct_sole_author": round(sole_commits / tc * 100, 1) if tc > 0 else 0,
            }
        return result

    def _top_n(counter, n=20):
        return [{"name": k, "count": v} for k, v in counter.most_common(n)]

    # Top surviving rules
    top_surviving = _build_top_surviving_rules(survival_by_rule, survival_by_rule_total)
    focused_top_surviving = _build_top_surviving_rules(
        focused_survival_by_rule,
        focused_survival_by_rule_total,
    )

    # Build cumulative survival-by-month time series
    def _build_survival_over_time(
        by_month: Dict[str, Dict[str, int]],
        by_month_family: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None,
    ) -> List[Dict]:
        """Cumulative survival: for issues introduced up to each month, what % survive?"""
        months = sorted(by_month.keys())
        cum_total = 0
        cum_surviving = 0
        cum_fam: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "surviving": 0})
        series = []
        for m in months:
            cum_total += by_month[m]["total"]
            cum_surviving += by_month[m]["surviving"]
            entry: Dict[str, Any] = {
                "month": m,
                "total": by_month[m]["total"],
                "surviving": by_month[m]["surviving"],
                "cum_total": cum_total,
                "cum_surviving": cum_surviving,
                "cum_survival_rate": round(cum_surviving / cum_total, 4) if cum_total > 0 else 0,
                "monthly_survival_rate": round(by_month[m]["surviving"] / by_month[m]["total"], 4)
                    if by_month[m]["total"] > 0 else 0,
            }
            if by_month_family is not None:
                fam_data = by_month_family.get(m, {})
                by_fam: Dict[str, Any] = {}
                for fam in ("bug", "code_smell", "security"):
                    fd = fam_data.get(fam, {"total": 0, "surviving": 0})
                    cum_fam[fam]["total"] += fd["total"]
                    cum_fam[fam]["surviving"] += fd["surviving"]
                    ft = fd["total"]
                    by_fam[fam] = {
                        "total": ft,
                        "surviving": fd["surviving"],
                        "monthly_rate": round(fd["surviving"] / ft, 4) if ft > 0 else 0,
                        "cum_total": cum_fam[fam]["total"],
                        "cum_surviving": cum_fam[fam]["surviving"],
                        "cum_rate": round(cum_fam[fam]["surviving"] / cum_fam[fam]["total"], 4)
                            if cum_fam[fam]["total"] > 0 else 0,
                    }
                entry["by_family"] = by_fam
            series.append(entry)
        return series

    survival_over_time = _build_survival_over_time(survival_by_month)
    focused_survival_over_time = _build_survival_over_time(
        focused_survival_by_month, focused_survival_by_month_family
    )

    def _build_survival_by_age(
        by_month: Dict[str, Dict[str, int]],
        by_month_family: Optional[Dict[str, Dict[str, Dict[str, int]]]] = None,
        monthly_commits: Optional[Dict[str, int]] = None,
        reference_month: str = "",
    ) -> List[Dict]:
        """Group survival by age cohort (how old issues are), not by calendar month."""
        from datetime import datetime
        if not reference_month:
            all_months = sorted(by_month.keys())
            reference_month = all_months[-1] if all_months else "2026-03"
        try:
            ref_dt = datetime.strptime(reference_month + "-01", "%Y-%m-%d")
        except ValueError:
            ref_dt = datetime(2026, 3, 1)

        # Age buckets: label, min_months_old, max_months_old (exclusive)
        buckets = [
            ("> 9 months", 9, 999),
            ("6\u20139 months", 6, 9),
            ("3\u20136 months", 3, 6),
            ("< 3 months", 0, 3),
        ]
        mc = monthly_commits or {}
        results = []
        for label, min_age, max_age in buckets:
            totals = {"total": 0, "surviving": 0}
            bucket_commits = 0
            fam_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "surviving": 0})
            for m, d in by_month.items():
                try:
                    m_dt = datetime.strptime(m + "-01", "%Y-%m-%d")
                except ValueError:
                    continue
                age_months = (ref_dt.year - m_dt.year) * 12 + (ref_dt.month - m_dt.month)
                if min_age <= age_months < max_age:
                    totals["total"] += d["total"]
                    totals["surviving"] += d["surviving"]
                    bucket_commits += mc.get(m, 0)
                    if by_month_family:
                        for fam in ("bug", "code_smell", "security"):
                            fd = by_month_family.get(m, {}).get(fam, {"total": 0, "surviving": 0})
                            fam_totals[fam]["total"] += fd["total"]
                            fam_totals[fam]["surviving"] += fd["surviving"]
            surv = totals["surviving"]
            entry: Dict[str, Any] = {
                "label": label,
                "total": totals["total"],
                "surviving": surv,
                "fixed": totals["total"] - surv,
                "commits": bucket_commits,
                "survival_rate": round(surv / totals["total"], 4) if totals["total"] > 0 else 0,
                "surviving_per_100_commits": round(surv / bucket_commits * 100, 2) if bucket_commits > 0 else 0,
            }
            if by_month_family:
                entry["by_family"] = {}
                for fam in ("bug", "code_smell", "security"):
                    ft = fam_totals[fam]["total"]
                    fs = fam_totals[fam]["surviving"]
                    entry["by_family"][fam] = {
                        "total": ft,
                        "surviving": fs,
                        "rate": round(fs / ft, 4) if ft > 0 else 0,
                        "surviving_per_100_commits": round(fs / bucket_commits * 100, 2) if bucket_commits > 0 else 0,
                    }
            results.append(entry)
        return results

    survival_by_age = _build_survival_by_age(
        survival_by_month, monthly_commits=dict(monthly_commits),
    )

    # High-debt commits: sort by high severity first, then total
    high_debt_commits.sort(key=lambda x: (x.get("high", 0), x["issues"]), reverse=True)

    # Build time-series sorted by month
    all_months = sorted(set(monthly_commits.keys()) | set(monthly_issues.keys()))
    time_series = []
    for m in all_months:
        entry = {
            "month": m,
            "commits": monthly_commits.get(m, 0),
            "issues": monthly_issues.get(m, 0),
            "high_issues": monthly_high.get(m, 0),
        }
        # Add per-tool breakdown (commits, issues, high)
        for tool in sorted(tool_commits.keys()):
            tc = monthly_by_tool[tool].get(m, 0)
            ti = monthly_issues_by_tool[tool].get(m, 0)
            th = monthly_high_by_tool[tool].get(m, 0)
            entry[f"tool_{tool}"] = tc
            entry[f"issues_{tool}"] = ti
            entry[f"high_{tool}"] = th
            # Issues per commit rate for this tool in this month
            entry[f"rate_{tool}"] = round(ti / tc, 2) if tc > 0 else 0
        time_series.append(entry)

    # Top rules with severity breakdown (actionable only — exclude noise)
    top_rules_detailed = []
    for rule, count in rule_counts.most_common(100):
        if rule in ALL_NOISE_RULES:
            continue
        sev_breakdown = dict(rule_sev_counts[rule])
        top_rules_detailed.append({
            "name": rule,
            "description": BANDIT_RULE_NAMES.get(rule, ""),
            "count": count,
            "high": sev_breakdown.get("high", 0),
            "medium": sev_breakdown.get("medium", 0),
            "low": sev_breakdown.get("low", 0),
        })
        if len(top_rules_detailed) >= 25:
            break

    # Build per-role detailed breakdowns
    def _build_role_detail(
        role,
        *,
        commits_counter: Counter,
        issues_counter: Counter,
        fixed_counter: Counter,
        high_counter: Counter,
        security_counter: Counter,
        files_counter: Counter,
        zero_counter: Counter,
        sev_counter_map: Dict[str, Counter],
        type_counter_map: Dict[str, Counter],
        lang_counter_map: Dict[str, Counter],
        rule_counter_map: Dict[str, Counter],
        rule_sev_map: Dict[str, Dict[str, Counter]],
        tool_role_commits_map: Dict[str, Counter],
        tool_role_issues_map: Dict[str, Counter],
        tool_role_issues_list_map: Dict[str, Dict[str, List[int]]],
        tool_role_files_map: Dict[str, Counter],
        tool_role_zero_map: Dict[str, Counter],
        monthly_commits_map: Dict[str, Counter],
        monthly_issues_map: Dict[str, Counter],
        monthly_high_map: Dict[str, Counter],
    ):
        """Build the full breakdown dict for a single author role."""
        rc = commits_counter[role]
        ri = issues_counter[role]
        rf = fixed_counter[role]

        # Top rules for this role (with severity breakdown)
        role_top_rules = []
        for rule, count in rule_counter_map[role].most_common(25):
            rsev = dict(rule_sev_map[role][rule])
            role_top_rules.append({
                "name": rule, "count": count,
                "high": rsev.get("high", 0),
                "medium": rsev.get("medium", 0),
                "low": rsev.get("low", 0),
            })

        # Per-tool stats restricted to this role
        role_tool_data = {}
        for t in sorted(tool_role_commits_map.keys()):
            tc_r = tool_role_commits_map[t].get(role, 0)
            if tc_r == 0:
                continue
            ti_r = tool_role_issues_map[t].get(role, 0)
            tf_r = tool_role_files_map[t].get(role, 0)
            tz_r = tool_role_zero_map[t].get(role, 0)
            per_commit_r = tool_role_issues_list_map[t].get(role, [])
            role_tool_data[t] = {
                "commits": tc_r,
                "issues_total": ti_r,
                "issues_per_commit_mean": round(ti_r / tc_r, 2) if tc_r > 0 else 0,
                "issues_per_commit_median": round(sorted(per_commit_r)[len(per_commit_r) // 2], 2) if per_commit_r else 0,
                "files_analyzed": tf_r,
                "files_per_commit": round(tf_r / tc_r, 2) if tc_r > 0 else 0,
                "issues_per_file": round(ti_r / tf_r, 2) if tf_r > 0 else 0,
                "zero_issue_pct": round(100 * tz_r / tc_r, 1) if tc_r > 0 else 0,
            }

        # Time series for this role
        role_months = sorted(
            set(monthly_commits_map[role].keys()) | set(monthly_issues_map[role].keys())
        )
        role_ts = []
        for m in role_months:
            role_ts.append({
                "month": m,
                "commits": monthly_commits_map[role].get(m, 0),
                "issues": monthly_issues_map[role].get(m, 0),
                "high_issues": monthly_high_map[role].get(m, 0),
            })

        rf_total = files_counter[role]
        rz = zero_counter[role]

        return {
            "commits": rc,
            "issues": ri,
            "issues_fixed": rf,
            "issues_high": high_counter[role],
            "issues_security": security_counter[role],
            "issues_per_commit": round(ri / rc, 2) if rc > 0 else 0,
            "net_debt": ri - rf,
            # Normalized metrics
            "files_analyzed": rf_total,
            "files_per_commit": round(rf_total / rc, 2) if rc > 0 else 0,
            "issues_per_file": round(ri / rf_total, 2) if rf_total > 0 else 0,
            "high_per_file": round(high_counter[role] / rf_total, 4) if rf_total > 0 else 0,
            "security_per_file": round(security_counter[role] / rf_total, 4) if rf_total > 0 else 0,
            "zero_issue_commits": rz,
            "zero_issue_pct": round(100 * rz / rc, 1) if rc > 0 else 0,
            "fix_rate": round(100 * rf / ri, 1) if ri > 0 else 0,
            # Breakdowns
            "by_severity": dict(sev_counter_map[role]),
            "by_type": dict(type_counter_map[role].most_common(20)),
            "by_language": dict(lang_counter_map[role]),
            "top_rules": role_top_rules,
            "by_tool": role_tool_data,
            "time_series": role_ts,
        }

    # Build result
    elapsed = round(time.time() - start, 1)
    likely_false_positive = sum(false_positive_counts.values())
    low_signal = sum(low_signal_rule_counts.values())

    false_positive_patterns = {
        "summary": {
            "total_issues": total_issues_introduced,
            "likely_false_positive": likely_false_positive,
            "low_signal": low_signal,
            "filtered_total": likely_false_positive + low_signal,
            "filtered_rate": round((likely_false_positive + low_signal) / total_issues_introduced * 100, 1) if total_issues_introduced > 0 else 0.0,
            "visible_by_default": max(0, total_issues_introduced - likely_false_positive - low_signal),
            "visible_rate": round(max(0, total_issues_introduced - likely_false_positive - low_signal) / total_issues_introduced * 100, 1) if total_issues_introduced > 0 else 0.0,
        },
        "patterns": [
            {
                "id": pattern_id,
                "label": FALSE_POSITIVE_PATTERN_META[pattern_id]["label"],
                "category": FALSE_POSITIVE_PATTERN_META[pattern_id]["category"],
                "description": FALSE_POSITIVE_PATTERN_META[pattern_id]["description"],
                "count": count,
                "share_pct": round(count / total_issues_introduced * 100, 1) if total_issues_introduced > 0 else 0.0,
                "top_rules": [
                    {"name": rule_name, "count": rule_count, "description": BANDIT_RULE_NAMES.get(rule_name, "")}
                    for rule_name, rule_count in false_positive_rule_counts[pattern_id].most_common(5)
                ],
                "sample_paths": false_positive_samples[pattern_id],
            }
            for pattern_id, count in false_positive_counts.most_common()
        ],
        "low_signal_rules": [
            {
                "name": rule_name,
                "description": BANDIT_RULE_NAMES.get(rule_name, ""),
                "count": count,
                "share_pct": round(count / total_issues_introduced * 100, 1) if total_issues_introduced > 0 else 0.0,
                "sample_paths": low_signal_samples[rule_name],
            }
            for rule_name, count in low_signal_rule_counts.most_common(15)
        ],
    }

    result = {
        "_generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "_elapsed_seconds": elapsed,
        "_repos_scanned": len(all_repos),

        # ── Global Totals ──
        "totals": {
            "repos": len(all_repos),
            "repos_with_code": repos_with_code,
            "commits": total_commits,
            "issues_introduced": total_issues_introduced,
            "issues_fixed": total_issues_fixed,
            "net_debt": total_issues_introduced - total_issues_fixed,
            "files_analyzed": total_files_analyzed,
            "files_per_commit": round(total_files_analyzed / total_commits, 2) if total_commits > 0 else 0,
            "issues_per_file": round(total_issues_introduced / total_files_analyzed, 2) if total_files_analyzed > 0 else 0,
            "fix_rate": round(100 * total_issues_fixed / total_issues_introduced, 1) if total_issues_introduced > 0 else 0,
            "actionable_introduced": actionable_introduced,
            "actionable_fixed": actionable_fixed,
            "actionable_by_severity": dict(actionable_sev),
            "actionable_fixed_by_severity": dict(actionable_fixed_sev),
            "actionable_net_debt": actionable_introduced - actionable_fixed,
            "actionable_by_type": dict(actionable_type.most_common(20)),
            "actionable_by_language": dict(actionable_lang),
        },

        # ── RQ1: What issues does AI code introduce? ──
        "rq1_debt_types": {
            "by_severity": dict(sev_counts),
            "by_family": dict(family_counts),
            "by_type": dict(type_counts.most_common(20)),
            "by_language": dict(lang_counts),
            "top_rules": top_rules_detailed,
            "security_total": sum(tool_security.values()),
            "security_pct": round(sum(tool_security.values()) / total_issues_introduced * 100, 1) if total_issues_introduced > 0 else 0,
        },

        # ── Time Series ──
        "time_series": time_series,

        # ── By Author Role ──
        "by_role": {
            role: _build_role_detail(
                role,
                commits_counter=role_commits,
                issues_counter=role_issues,
                fixed_counter=role_fixed,
                high_counter=role_high,
                security_counter=role_security,
                files_counter=role_files,
                zero_counter=role_zero_commits,
                sev_counter_map=role_sev_counts,
                type_counter_map=role_type_counts,
                lang_counter_map=role_lang_counts,
                rule_counter_map=role_rule_counts,
                rule_sev_map=role_rule_sev,
                tool_role_commits_map=tool_role_commits,
                tool_role_issues_map=tool_role_issues,
                tool_role_issues_list_map=tool_role_issues_list,
                tool_role_files_map=tool_role_files,
                tool_role_zero_map=tool_role_zero,
                monthly_commits_map=role_monthly_commits,
                monthly_issues_map=role_monthly_issues,
                monthly_high_map=role_monthly_high,
            )
            for role in ("sole_author", "coauthor", "unknown")
            if role_commits[role] > 0
        },

        # ── RQ2: How do AI tools compare? ──
        "rq2_tool_comparison": {
            "by_tool": _per_tool_stats(),
            "tools_ranked_by_issues_per_commit": sorted(
                [{"tool": t, "rate": round(tool_issues[t] / tool_commits[t], 2) if tool_commits[t] > 0 else 0}
                 for t in tool_commits],
                key=lambda x: x["rate"], reverse=True,
            ),
        },

        # ── RQ3: Do issues survive? ──
        "rq3_survival": {
            "issue_survival": {
                "total_tracked": survival_total,
                "surviving": survival_surviving,
                "fixed": survival_total - survival_surviving,
                "survival_rate": round(survival_surviving / survival_total, 4) if survival_total > 0 else 0,
            },
            "by_severity": {
                sev: {
                    "total": d["total"],
                    "surviving": d["surviving"],
                    "rate": round(d["surviving"] / d["total"], 4) if d["total"] > 0 else 0,
                }
                for sev, d in sorted(survival_by_sev.items())
            },
            "by_family": {
                fam: {
                    "total": d["total"],
                    "surviving": d["surviving"],
                    "fixed": d["total"] - d["surviving"],
                    "rate": round(d["surviving"] / d["total"], 4) if d["total"] > 0 else 0,
                }
                for fam, d in sorted(survival_by_family.items())
            },
            "by_tool": {
                tool: {
                    "total": d["total"],
                    "surviving": d["surviving"],
                    "rate": round(d["surviving"] / d["total"], 4) if d["total"] > 0 else 0,
                }
                for tool, d in sorted(survival_by_tool.items())
                if d["total"] >= 10
            },
            "top_surviving_rules": top_surviving,
            "survival_over_time": survival_over_time,
            "survival_by_age": survival_by_age,
            "line_survival": _stats(line_survival_rates),
            "semantic_survival": _stats(semantic_survival_rates),
            "per_repo_survival_distribution": _stats([r["rate"] for r in per_repo_survival]),
        },

        # ── File Lifecycle ──
        "file_lifecycle": {
            "total_files": files_survived + files_modified + files_deleted,
            "survived": files_survived,
            "modified": files_modified,
            "deleted": files_deleted,
            "had_fixes": files_fixed,
            "refactored": files_refactored,
        },

        # ── Distribution ──
        "distributions": {
            "issues_per_repo": _stats(repo_issue_rates),
            "line_survival_per_commit": _stats(line_survival_rates),
            "semantic_survival_per_commit": _stats(semantic_survival_rates),
        },

        "false_positive_patterns": false_positive_patterns,

        # ── Notable ──
        "notable": {
            "high_debt_commits": high_debt_commits[:20],
            "top_repos_by_issues": sorted(all_repos, key=lambda r: r["issues_introduced"], reverse=True)[:15],
            "repos_zero_issues": sum(1 for r in all_repos if r["issues_introduced"] == 0),
            "all_repos": sorted(
                [r for r in all_repos if r["issues_introduced"] > 0],
                key=lambda r: r["issues_introduced"],
                reverse=True,
            ),
        },
    }

    # ── Focused Tools (top 5 mainstream AI coding agents) ──
    focused_by_tool = {t: v for t, v in result["rq2_tool_comparison"]["by_tool"].items() if t in FOCUSED_TOOLS}

    f_commits = sum(v.get("commits", 0) for v in focused_by_tool.values())
    f_issues = sum(v.get("issues_total", 0) for v in focused_by_tool.values())
    f_files = sum(v.get("files_analyzed", 0) for v in focused_by_tool.values())
    f_zero = sum(v.get("zero_issue_commits", 0) for v in focused_by_tool.values())

    f_sev: Counter = Counter()
    f_type: Counter = Counter()
    f_lang: Counter = Counter()
    f_fixed = 0
    f_fixed_sev: Counter = Counter()
    f_rule: Counter = Counter()
    f_rule_sev: Dict[str, Counter] = defaultdict(Counter)
    f_repos_set: set = set()
    f_repos_with_code: set = set()
    f_actionable_intro = 0
    f_actionable_fixed = 0
    f_actionable_sev: Counter = Counter()
    f_actionable_fixed_sev: Counter = Counter()
    f_actionable_type: Counter = Counter()
    f_family: Counter = Counter()
    f_actionable_lang: Counter = Counter()
    f_tool_actionable: Counter = Counter()  # per-tool actionable issues
    f_tool_repos_with_code: Dict[str, set] = defaultdict(set)  # per-tool repos with code
    f_tool_family: Dict[str, Counter] = defaultdict(Counter)   # tool -> {bug/code_smell/security: count}
    f_tool_files: Counter = Counter()                          # tool -> files analyzed
    f_monthly_tool_commits: Dict[str, Counter] = defaultdict(Counter)  # month -> {tool: commits}
    f_monthly_tool_issues: Dict[str, Counter] = defaultdict(Counter)   # month -> {tool: actionable issues}
    f_family_rules: Dict[str, Counter] = defaultdict(Counter)  # family -> {rule: count}
    f_family_repos: Dict[str, set] = defaultdict(set)         # family -> set of repos
    f_family_commits: Dict[str, set] = defaultdict(set)       # family -> set of commit SHAs
    f_repos_with_issues: set = set()                           # repos with any actionable issue
    f_commits_with_issues: set = set()                         # commits with any actionable issue
    f_family_fixed: Counter = Counter()                       # family -> fixed issue count
    f_lang_rules: Dict[str, Counter] = defaultdict(Counter)   # lang -> {rule: count}
    f_lang_family: Dict[str, Counter] = defaultdict(Counter)  # lang -> {family: count}
    f_likely_false_positive = 0
    f_low_signal = 0
    f_filtered_rule_counts: Counter = Counter()

    for repo_dir in sorted([d for d in out_path.iterdir() if d.is_dir() and (d / "debt_metrics.json").exists()]):
        debt_data = load_json(str(repo_dir / "debt_metrics.json"))
        if not isinstance(debt_data, list):
            continue
        repo_name = repo_dir.name.replace("_", "/", 1)
        for commit in debt_data:
            if is_tainted_commit(commit):
                continue
            tool = commit.get("ai_tool") or "unknown"
            if tool not in FOCUSED_TOOLS:
                continue
            f_repos_set.add(repo_name)
            sha = (commit.get("commit_hash") or "")[:12]
            month = commit_dates.get(sha, "")
            if month >= "2024-01":
                f_monthly_tool_commits[month][tool] += 1
            n_code = commit.get("code_files_analyzed") or len(commit.get("files", []))
            if n_code > 0:
                f_repos_with_code.add(repo_name)
                f_tool_repos_with_code[tool].add(repo_name)
            for f in commit.get("files", []):
                if is_noise_path(f.get("file_path", "")):
                    continue
                f_tool_files[tool] += 1
                for issue in _filter_file_issues(f, "issues_added"):
                    sev_n = normalize_severity(issue)
                    itype = (issue.get("type") or issue.get("detected_by") or "unknown").lower()
                    rule = issue.get("symbol") or issue.get("rule") or issue.get("rule_id") or "unknown"
                    file_path = f.get("file_path") or ""
                    lang = language_from_path(file_path)
                    issue_is_low_signal = is_issue_low_signal(issue, file_path=file_path)
                    f_sev[sev_n] += 1
                    f_type[itype] += 1
                    f_lang[lang] += 1
                    fp = _classify_false_positive_pattern(file_path, rule)
                    if fp:
                        f_likely_false_positive += 1
                        f_filtered_rule_counts[rule] += 1
                    elif sev_n == "low" or issue_is_low_signal:
                        f_low_signal += 1
                        f_filtered_rule_counts[rule] += 1
                    if rule not in ALL_NOISE_RULES and not fp and not issue_is_low_signal:
                        f_actionable_intro += 1
                        f_actionable_sev[sev_n] += 1
                        f_actionable_type[itype] += 1
                        family = classify_issue_family(issue)
                        f_family[family] += 1
                        f_actionable_lang[lang] += 1
                        f_tool_actionable[tool] += 1
                        f_tool_family[tool][family] += 1
                        if month >= "2024-01":
                            f_monthly_tool_issues[month][tool] += 1
                        f_rule[rule] += 1
                        f_rule_sev[rule][sev_n] += 1
                        # Per-family rules, repos, commits
                        f_family_rules[family][rule] += 1
                        f_family_repos[family].add(repo_name)
                        f_family_commits[family].add(commit.get("commit_hash", "")[:12])
                        f_repos_with_issues.add(repo_name)
                        f_commits_with_issues.add(commit.get("commit_hash", "")[:12])
                        # Per-language rules and family
                        js_or_ts = "javascript" if lang in ("javascript", "typescript") else lang
                        f_lang_rules[js_or_ts][rule] += 1
                        f_lang_family[js_or_ts][family] += 1
                for issue in _filter_file_issues(f, "issues_resolved"):
                    f_fixed += 1
                    fsev = normalize_severity(issue)
                    f_fixed_sev[fsev] += 1
                    frule = issue.get("symbol") or issue.get("rule") or issue.get("rule_id") or ""
                    if frule not in ALL_NOISE_RULES:
                        f_actionable_fixed += 1
                        f_actionable_fixed_sev[fsev] += 1
                        fixed_family = classify_issue_family(issue)
                        f_family_fixed[fixed_family] += 1

    f_top_rules = []
    for rule, count in f_rule.most_common(100):
        if rule in ALL_NOISE_RULES:
            continue
        rsev = dict(f_rule_sev[rule])
        f_top_rules.append({
            "name": rule,
            "description": BANDIT_RULE_NAMES.get(rule, ""),
            "count": count,
            "high": rsev.get("high", 0),
            "medium": rsev.get("medium", 0),
            "low": rsev.get("low", 0),
        })
        if len(f_top_rules) >= 25:
            break

    f_security = sum(v.get("issues_security", 0) for v in focused_by_tool.values())

    # Inject per-tool actionable counts, family breakdown, and repos_with_code
    for tool_key in focused_by_tool:
        act = f_tool_actionable.get(tool_key, 0)
        files = f_tool_files.get(tool_key, 0)
        commits = focused_by_tool[tool_key].get("commits", 0)
        fam = f_tool_family.get(tool_key, Counter())
        focused_by_tool[tool_key]["actionable_issues"] = act
        focused_by_tool[tool_key]["repos_with_code"] = len(f_tool_repos_with_code.get(tool_key, set()))
        focused_by_tool[tool_key]["actionable_files"] = files
        focused_by_tool[tool_key]["bugs"] = fam.get("bug", 0)
        focused_by_tool[tool_key]["smells"] = fam.get("code_smell", 0)
        focused_by_tool[tool_key]["security_issues"] = fam.get("security", 0)
        focused_by_tool[tool_key]["bugs_per_commit"] = round(fam.get("bug", 0) / commits, 3) if commits else 0
        focused_by_tool[tool_key]["smells_per_commit"] = round(fam.get("code_smell", 0) / commits, 3) if commits else 0
        focused_by_tool[tool_key]["security_per_commit"] = round(fam.get("security", 0) / commits, 3) if commits else 0
        focused_by_tool[tool_key]["actionable_per_commit"] = round(act / commits, 3) if commits else 0
        focused_by_tool[tool_key]["actionable_per_file"] = round(act / files, 3) if files else 0
        focused_by_tool[tool_key]["bugs_per_file"] = round(fam.get("bug", 0) / files, 4) if files else 0
        focused_by_tool[tool_key]["smells_per_file"] = round(fam.get("code_smell", 0) / files, 4) if files else 0
        focused_by_tool[tool_key]["security_per_file"] = round(fam.get("security", 0) / files, 4) if files else 0

    # Build per-repo stats for star/language analysis
    _repo_stats: Dict[str, Dict] = {}
    for repo_dir in sorted([d for d in out_path.iterdir() if d.is_dir() and (d / "debt_metrics.json").exists()]):
        debt_data = load_json(str(repo_dir / "debt_metrics.json"))
        if not isinstance(debt_data, list):
            continue
        repo_name = repo_dir.name.replace("_", "/", 1)
        rmeta = repo_meta.get(repo_name, {})
        stars = rmeta.get("stars", 0)
        lang = rmeta.get("language", "")
        r_commits = 0
        r_bugs = 0
        r_smells = 0
        r_sec = 0
        r_has_code = False
        for commit in debt_data:
            if is_tainted_commit(commit):
                continue
            tool = commit.get("ai_tool") or "unknown"
            if tool not in FOCUSED_TOOLS:
                continue
            if (commit.get("code_files_analyzed") or len(commit.get("files", []))) > 0:
                r_has_code = True
            r_commits += 1
            for fi in commit.get("files", []):
                if is_noise_path(fi.get("file_path", "")):
                    continue
                for issue in _filter_file_issues(fi, "issues_added"):
                    rule = issue.get("symbol") or issue.get("rule") or issue.get("rule_id") or "unknown"
                    if rule in ALL_NOISE_RULES:
                        continue
                    fp = _classify_false_positive_pattern(fi.get("file_path", ""), rule)
                    if fp or is_issue_low_signal(issue, file_path=fi.get("file_path", "")):
                        continue
                    fam = classify_issue_family(issue)
                    if fam == "bug":
                        r_bugs += 1
                    elif fam == "code_smell":
                        r_smells += 1
                    elif fam == "security":
                        r_sec += 1
        if r_commits > 0 and r_has_code:
            _repo_stats[repo_name] = {"stars": stars, "language": lang, "commits": r_commits,
                                       "bugs": r_bugs, "smells": r_smells, "security": r_sec}

    # By star bucket
    star_buckets_def = [("100-500", 100, 500), ("500-1K", 500, 1000), ("1K-5K", 1000, 5000),
                        ("5K-10K", 5000, 10000), ("10K-50K", 10000, 50000), ("50K+", 50000, 10**9)]
    by_stars = []
    for label, lo, hi in star_buckets_def:
        matching = [r for r in _repo_stats.values() if lo <= r["stars"] < hi]
        if not matching:
            continue
        tc = sum(r["commits"] for r in matching)
        tb = sum(r["bugs"] for r in matching)
        ts = sum(r["smells"] for r in matching)
        tsc = sum(r["security"] for r in matching)
        by_stars.append({"label": label, "repos": len(matching), "commits": tc,
                         "bugs": tb, "smells": ts, "security": tsc,
                         "bugs_per_commit": round(tb / tc, 4) if tc else 0,
                         "smells_per_commit": round(ts / tc, 4) if tc else 0,
                         "security_per_commit": round(tsc / tc, 4) if tc else 0,
                         "total_per_commit": round((tb + ts + tsc) / tc, 4) if tc else 0})

    # By language
    lang_agg: Dict[str, Dict] = defaultdict(lambda: {"repos": 0, "commits": 0, "bugs": 0, "smells": 0, "security": 0})
    for r in _repo_stats.values():
        lang = r["language"] if r["language"] in ("Python", "TypeScript", "JavaScript", "Go", "Rust",
                                                   "Java", "C++", "C#", "C", "Ruby", "PHP", "Kotlin") else "Other"
        la = lang_agg[lang]
        la["repos"] += 1
        la["commits"] += r["commits"]
        la["bugs"] += r["bugs"]
        la["smells"] += r["smells"]
        la["security"] += r["security"]
    by_language_breakdown = []
    for lang in sorted(lang_agg.keys(), key=lambda x: -lang_agg[x]["commits"]):
        la = lang_agg[lang]
        if la["repos"] < 5:
            continue
        tc = la["commits"]
        by_language_breakdown.append({"language": lang, "repos": la["repos"], "commits": tc,
                                      "bugs": la["bugs"], "smells": la["smells"], "security": la["security"],
                                      "bugs_per_commit": round(la["bugs"] / tc, 4) if tc else 0,
                                      "smells_per_commit": round(la["smells"] / tc, 4) if tc else 0,
                                      "security_per_commit": round(la["security"] / tc, 4) if tc else 0,
                                      "total_per_commit": round((la["bugs"] + la["smells"] + la["security"]) / tc, 4) if tc else 0})

    # Build focused survival by age (needs f_monthly_tool_commits)
    focused_monthly_commit_totals: Dict[str, int] = {}
    for m, tool_counts in f_monthly_tool_commits.items():
        focused_monthly_commit_totals[m] = sum(tool_counts.values())
    focused_survival_by_age = _build_survival_by_age(
        focused_survival_by_month, focused_survival_by_month_family,
        monthly_commits=focused_monthly_commit_totals,
    )

    result["focused"] = {
        "tools": sorted(FOCUSED_TOOLS),
        "totals": {
            "repos": len(f_repos_with_code),
            "repos_with_code": len(f_repos_with_code),
            "repos_all": len(f_repos_set),
            "commits": f_commits,
            "issues_introduced": f_issues,
            "issues_fixed": f_fixed,
            "issues_fixed_by_severity": dict(f_fixed_sev),
            "net_debt": f_issues - f_fixed,
            "files_analyzed": f_files,
            "files_per_commit": round(f_files / f_commits, 2) if f_commits > 0 else 0,
            "issues_per_file": round(f_issues / f_files, 2) if f_files > 0 else 0,
            "fix_rate": round(100 * f_fixed / f_issues, 1) if f_issues > 0 else 0,
            "zero_issue_pct": round(100 * f_zero / f_commits, 1) if f_commits > 0 else 0,
            "actionable_introduced": f_actionable_intro,
            "actionable_fixed": f_actionable_fixed,
            "actionable_by_severity": dict(f_actionable_sev),
            "actionable_fixed_by_severity": dict(f_actionable_fixed_sev),
            "actionable_net_debt": f_actionable_intro - f_actionable_fixed,
            "repos_with_issues": len(f_repos_with_issues),
            "commits_with_issues": len(f_commits_with_issues),
        },
        "by_severity": dict(f_sev),
        "by_family": {
            fam: {
                "issues": f_family.get(fam, 0),
                "fixed": f_family_fixed.get(fam, 0),
                "net": f_family.get(fam, 0) - f_family_fixed.get(fam, 0),
                "repos": len(f_family_repos.get(fam, set())),
                "commits": len(f_family_commits.get(fam, set())),
            }
            for fam in ("bug", "code_smell", "security")
        },
        "top_rules_by_family": {
            fam: [
                {"name": r, "count": c, "description": BANDIT_RULE_NAMES.get(r, "")}
                for r, c in f_family_rules[fam].most_common(10)
            ]
            for fam in ("bug", "code_smell", "security")
            if f_family_rules[fam]
        },
        "all_rules_by_family": {
            fam: [
                {"name": r, "count": c, "description": BANDIT_RULE_NAMES.get(r, "")}
                for r, c in f_family_rules[fam].most_common()
            ]
            for fam in ("bug", "code_smell", "security")
            if f_family_rules[fam]
        },
        "by_type": dict(f_actionable_type.most_common(20)),
        "by_language": dict(f_actionable_lang),
        "top_rules_by_language": {
            lang: [
                {"name": r, "count": c, "description": BANDIT_RULE_NAMES.get(r, "")}
                for r, c in f_lang_rules[lang].most_common(10)
            ]
            for lang in ("python", "javascript")
            if f_lang_rules[lang]
        },
        "family_by_language": {
            lang: dict(f_lang_family[lang])
            for lang in ("python", "javascript")
            if f_lang_family[lang]
        },
        "top_rules": f_top_rules,
        "by_stars": by_stars,
        "by_language_breakdown": by_language_breakdown,
        "security_total": f_security,
        "by_tool": focused_by_tool,
        "filtering": {
            "summary": {
                "total_issues": f_issues,
                "likely_false_positive": f_likely_false_positive,
                "low_signal": f_low_signal,
                "filtered_total": f_likely_false_positive + f_low_signal,
                "filtered_rate": round((f_likely_false_positive + f_low_signal) / f_issues * 100, 1) if f_issues > 0 else 0.0,
                "visible_by_default": max(0, f_issues - f_likely_false_positive - f_low_signal),
                "visible_rate": round(max(0, f_issues - f_likely_false_positive - f_low_signal) / f_issues * 100, 1) if f_issues > 0 else 0.0,
            },
            "filtered_rules": [
                {
                    "name": rule_name,
                    "description": BANDIT_RULE_NAMES.get(rule_name, ""),
                    "count": count,
                    "share_pct": round(count / f_issues * 100, 1) if f_issues > 0 else 0.0,
                    "filtered_share_pct": round(count / (f_likely_false_positive + f_low_signal) * 100, 1) if (f_likely_false_positive + f_low_signal) > 0 else 0.0,
                }
                for rule_name, count in f_filtered_rule_counts.most_common(15)
            ],
        },
        # Focused time series: actionable issues only, per tool, study period
        "time_series": sorted([
            {
                "month": m,
                "commits": sum(f_monthly_tool_commits[m].get(t, 0) for t in FOCUSED_TOOLS),
                "issues": sum(f_monthly_tool_issues[m].get(t, 0) for t in FOCUSED_TOOLS),
                **{f"tool_{t}": f_monthly_tool_commits[m].get(t, 0) for t in sorted(FOCUSED_TOOLS)},
                **{f"issues_{t}": f_monthly_tool_issues[m].get(t, 0) for t in sorted(FOCUSED_TOOLS)},
                **{f"rate_{t}": round(f_monthly_tool_issues[m].get(t, 0) / f_monthly_tool_commits[m].get(t, 1), 2)
                   if f_monthly_tool_commits[m].get(t, 0) > 0 else 0
                   for t in sorted(FOCUSED_TOOLS)},
            }
            for m in set(f_monthly_tool_commits.keys()) | set(f_monthly_tool_issues.keys())
            if m >= "2024-01"
        ], key=lambda x: x["month"]),
        "survival": {
            "total_tracked": focused_survival_total,
            "surviving": focused_survival_surviving,
            "fixed": focused_survival_total - focused_survival_surviving,
            "survival_rate": round(focused_survival_surviving / focused_survival_total, 4) if focused_survival_total > 0 else 0,
            "issue_survival": {
                "total_tracked": focused_survival_total,
                "surviving": focused_survival_surviving,
                "fixed": focused_survival_total - focused_survival_surviving,
                "survival_rate": round(focused_survival_surviving / focused_survival_total, 4) if focused_survival_total > 0 else 0,
            },
            "by_severity": {
                sev: {
                    "total": d["total"],
                    "surviving": d["surviving"],
                    "rate": round(d["surviving"] / d["total"], 4) if d["total"] > 0 else 0,
                }
                for sev, d in sorted(focused_survival_by_sev.items())
            },
            "by_family": {
                fam: {
                    "total": d["total"],
                    "surviving": d["surviving"],
                    "fixed": d["total"] - d["surviving"],
                    "rate": round(d["surviving"] / d["total"], 4) if d["total"] > 0 else 0,
                }
                for fam, d in sorted(focused_survival_by_family.items())
            },
            "by_tool": {
                t: result["rq3_survival"]["by_tool"].get(t, {"total": 0, "surviving": 0, "rate": 0})
                for t in FOCUSED_TOOLS
                if result["rq3_survival"]["by_tool"].get(t, {}).get("total", 0) > 0
            },
            "top_surviving_rules": focused_top_surviving,
            "survival_over_time": focused_survival_over_time,
            "survival_by_age": focused_survival_by_age,
            "line_survival": _stats(focused_line_survival_rates),
            "semantic_survival": _stats(focused_semantic_survival_rates),
            "per_repo_survival_distribution": _stats([r["rate"] for r in focused_per_repo_survival]),
        },
        "by_role": {
            role: _build_role_detail(
                role,
                commits_counter=focused_role_commits,
                issues_counter=focused_role_issues,
                fixed_counter=focused_role_fixed,
                high_counter=focused_role_high,
                security_counter=focused_role_security,
                files_counter=focused_role_files,
                zero_counter=focused_role_zero_commits,
                sev_counter_map=focused_role_sev_counts,
                type_counter_map=focused_role_type_counts,
                lang_counter_map=focused_role_lang_counts,
                rule_counter_map=focused_role_rule_counts,
                rule_sev_map=focused_role_rule_sev,
                tool_role_commits_map=focused_tool_role_commits,
                tool_role_issues_map=focused_tool_role_issues,
                tool_role_issues_list_map=focused_tool_role_issues_list,
                tool_role_files_map=focused_tool_role_files,
                tool_role_zero_map=focused_tool_role_zero,
                monthly_commits_map=focused_role_monthly_commits,
                monthly_issues_map=focused_role_monthly_issues,
                monthly_high_map=focused_role_monthly_high,
            )
            for role in ("sole_author", "coauthor", "unknown")
            if focused_role_commits[role] > 0
        },
        "file_lifecycle": {
            "total_files": focused_files_survived + focused_files_modified + focused_files_deleted,
            "survived": focused_files_survived,
            "modified": focused_files_modified,
            "deleted": focused_files_deleted,
            "had_fixes": focused_files_fixed,
            "refactored": focused_files_refactored,
        },
    }

    return result


def needs_update(out_dir: str, output_path: str) -> bool:
    """Check if aggregate summary needs re-computation (any repo data newer than cache)."""
    if not os.path.exists(output_path):
        return True
    agg_mtime = os.path.getmtime(output_path)

    # Invalidate the cache when filter config or aggregator code changes, so a
    # tweak to blocked_rules.py propagates to the dashboard on next refresh.
    code_watched = (
        os.path.join(os.path.dirname(__file__), "aggregate.py"),
        os.path.join(os.path.dirname(__file__), "..", "config", "blocked_rules.py"),
        os.path.join(os.path.dirname(__file__), "..", "filters.py"),
    )
    for path in code_watched:
        try:
            if os.path.getmtime(path) > agg_mtime:
                return True
        except OSError:
            pass

    watched_files = (
        "debt_metrics.json",
        "issue_survival.json",
        "destiny_metrics.json",
        "lifecycle_metrics.json",
    )
    try:
        for entry in os.scandir(out_dir):
            if entry.is_dir():
                for filename in watched_files:
                    file_path = os.path.join(entry.path, filename)
                    if os.path.exists(file_path) and os.path.getmtime(file_path) > agg_mtime:
                        return True
    except OSError:
        return True
    return False


def aggregate_and_save(out_dir: str, force: bool = False) -> Tuple[str, bool]:
    """
    Aggregate cross-repo statistics and save to JSON.
    
    This is the main API for other modules (e.g., dashboard server).
    Only re-computes if data has changed (or force=True).
    
    Args:
        out_dir: Pipeline output directory (e.g., "out")
        force: Re-compute even if cached file is up-to-date
        
    Returns:
        (output_path, was_recomputed)
    """
    output_path = os.path.join(out_dir, "aggregate_summary.json")

    if not force and not needs_update(out_dir, output_path):
        logger.info("Aggregate summary is up-to-date.")
        return output_path, False

    logger.info("Aggregating results from %s...", out_dir)
    result = aggregate(out_dir)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    logger.info("Saved aggregate summary to %s (%d repos, %d commits, %.1fs)",
                output_path, result["totals"]["repos"], result["totals"]["commits"],
                result["_elapsed_seconds"])
    return output_path, True


def main() -> int:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Aggregate cross-repo research statistics.")
    parser.add_argument("--out-dir", default="out", help="Pipeline output directory")
    parser.add_argument("--force", action="store_true", help="Re-compute even if cached")
    args = parser.parse_args()

    aggregate_and_save(args.out_dir, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
