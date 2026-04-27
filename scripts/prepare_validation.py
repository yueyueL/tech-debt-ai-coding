#!/usr/bin/env python3
"""
Prepare validation samples for the paper.

Two validation tasks (Section 4.4):
  1. AI Attribution Validation:
     - 200 commits (40 per tool) randomly sampled
     - Validate: is the commit correctly attributed to the claimed AI tool?

  2. Issue Detection & Survival Validation:
     - 100 introduced issues from 100 distinct AI-attributed commits
     - Validate: (a) is the issue real (not false positive)?
                 (b) is the survival classification at HEAD correct?

Outputs:
  data/validation/ai_identifying/
    - attribution_sample.csv   (200 rows for manual labeling)
    - attribution_sample.json  (full metadata for reference)

  data/validation/vul_check/
    - issue_sample.csv         (100 rows for manual labeling)
    - issue_sample.json        (full metadata for reference)
"""

import json
import os
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

# Add project root to path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.blocked_rules import (
    BLOCKED_RULES, LOW_SIGNAL_RULES, is_issue_low_signal, is_blocked,
)

# ── Config ──
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "out"
COMMITS_DIR = DATA_DIR / "commits"
VAL_DIR = DATA_DIR / "validation"

TOOLS = ["copilot", "claude", "cursor", "gemini", "devin"]
COMMITS_PER_TOOL = 40  # 200 total
ISSUE_SAMPLES = 100

SEED = 42

random.seed(SEED)


def load_all_commits():
    """Load all AI-attributed commits from data/commits/*.json."""
    commits_by_tool = defaultdict(list)

    for fname in sorted(os.listdir(COMMITS_DIR)):
        if not fname.endswith("_commits.json"):
            continue
        fpath = COMMITS_DIR / fname
        try:
            with open(fpath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        repo = data.get("repo", "")
        stars = data.get("stars", 0)

        for commit in data.get("ai_commits", []):
            tool = commit.get("ai_tool", "").lower()
            if tool not in TOOLS:
                continue

            commits_by_tool[tool].append({
                "sha": commit["sha"],
                "repo": repo,
                "ai_tool": tool,
                "detection_method": commit.get("detection_method", ""),
                "author_name": commit.get("author_name", ""),
                "author_email": commit.get("author_email", ""),
                "message": commit.get("message", "")[:300],
                "date": commit.get("date", ""),
                "url": commit.get("url", ""),
                "author_role": commit.get("author_role", ""),
                "ai_identifier": commit.get("ai_identifier", ""),
                "ai_identifier_type": commit.get("ai_identifier_type", ""),
                "stars": stars,
            })

    return commits_by_tool


def sample_commits(commits_by_tool):
    """Stratified random sample: 40 per tool."""
    sampled = []
    for tool in TOOLS:
        pool = commits_by_tool.get(tool, [])
        if len(pool) < COMMITS_PER_TOOL:
            print(f"  WARNING: {tool} has only {len(pool)} commits (need {COMMITS_PER_TOOL})")
            sampled.extend(pool)
        else:
            sampled.extend(random.sample(pool, COMMITS_PER_TOOL))

    random.shuffle(sampled)
    return sampled


def _build_commit_tool_index():
    """Build a fast sha→(tool, repo) index from data/commits/ files.

    This is much faster than loading debt_metrics.json from every out/ dir.
    """
    index = {}
    for fname in sorted(os.listdir(COMMITS_DIR)):
        if not fname.endswith("_commits.json"):
            continue
        try:
            with open(COMMITS_DIR / fname) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
        repo = data.get("repo", "")
        for commit in data.get("ai_commits", []):
            tool = commit.get("ai_tool", "").lower()
            if tool in TOOLS:
                index[commit["sha"]] = (tool, repo)
    return index


def load_issues_with_survival():
    """Load introduced issues with survival info from out/*/issue_survival.json."""
    print("    Building commit→tool index from data/commits/...")
    commit_index = _build_commit_tool_index()
    print(f"    Index built: {len(commit_index):,} commits")

    all_issues = []
    repos_scanned = 0

    repo_dirs = sorted(os.listdir(OUT_DIR))
    total_repos = len(repo_dirs)

    for repo_dir_name in repo_dirs:
        repo_path = OUT_DIR / repo_dir_name
        is_path = repo_path / "issue_survival.json"

        if not is_path.exists():
            continue

        try:
            with open(is_path) as f:
                surv_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        if "issues" not in surv_data:
            continue

        repos_scanned += 1
        if repos_scanned % 500 == 0:
            print(f"    Scanned {repos_scanned}/{total_repos} repos, {len(all_issues):,} issues so far...")

        for issue in surv_data["issues"]:
            orig = issue.get("original", {})
            commit_sha = orig.get("commit_sha", "")

            # Fast lookup from pre-built index
            info = commit_index.get(commit_sha)
            if info is None:
                continue
            tool, repo_name = info

            file_path = orig.get("file_path", "")
            line = orig.get("line", "")
            resolved_path = issue.get("resolved_path", "") or file_path
            current_line = ""
            if issue.get("current"):
                current_line = issue["current"].get("line", "")

            # Direct link to the file at commit, jumping to the issue line
            file_at_commit_url = f"https://github.com/{repo_name}/blob/{commit_sha}/{file_path}"
            if line:
                file_at_commit_url += f"#L{line}"

            # Direct link to the file at HEAD, jumping to the current line
            file_at_head_url = f"https://github.com/{repo_name}/blob/HEAD/{resolved_path}"
            if current_line:
                file_at_head_url += f"#L{current_line}"

            all_issues.append({
                "commit_sha": commit_sha,
                "repo": repo_name,
                "ai_tool": tool,
                "file_path": file_path,
                "line": line,
                "rule_id": orig.get("rule_id", ""),
                "issue_type": orig.get("type", ""),
                "severity": orig.get("severity", ""),
                "message": orig.get("message", ""),
                "survived": issue.get("survived", False),
                "match_score": issue.get("match_score", 0),
                "match_reason": issue.get("match_reason", ""),
                "resolved_path": resolved_path,
                "current_line": current_line,
                "commit_url": f"https://github.com/{repo_name}/commit/{commit_sha}",
                "file_at_commit_url": file_at_commit_url,
                "file_at_head_url": file_at_head_url,
            })

    return all_issues


import re

# Common ESLint message → rule mapping patterns
_ESLINT_MSG_RULES = [
    (re.compile(r"'(\w+)' is (assigned a value but never used|defined but never used)"), "no-unused-vars"),
    (re.compile(r"'(\w+)' is not defined"), "no-undef"),
    (re.compile(r"Unexpected var,"), "no-var"),
    (re.compile(r"has a complexity of \d+"), "complexity"),
    (re.compile(r"Unexpected console"), "no-console"),
    (re.compile(r"Expected '===' and instead saw '=='"), "eqeqeq"),
    (re.compile(r"Missing semicolon"), "semi"),
    (re.compile(r"Unreachable code"), "no-unreachable"),
    (re.compile(r"Duplicate key"), "no-dupe-keys"),
    (re.compile(r"Unnecessary semicolon"), "no-extra-semi"),
    (re.compile(r"Unexpected (constant|always)"), "no-constant-condition"),
    (re.compile(r"Empty block statement"), "no-empty"),
    (re.compile(r"self.compare|compared to itself"), "no-self-compare"),
    (re.compile(r"self.assign|assigned to itself"), "no-self-assign"),
    (re.compile(r"is already declared"), "no-redeclare"),
    (re.compile(r"Unexpected empty (?:arrow )?function"), "no-empty-function"),
    (re.compile(r"Missing return type"), "explicit-function-return-type"),
    (re.compile(r"Unexpected any"), "no-explicit-any"),
    (re.compile(r"shadowed"), "no-shadow"),
]


def _extract_eslint_rule(message: str, file_path: str = "") -> str:
    """Try to extract ESLint rule name from the message text."""
    for pattern, rule in _ESLINT_MSG_RULES:
        if pattern.search(message):
            return rule
    return ""


def sample_issues(all_issues):
    """Sample 100 issues from 100 distinct commits.

    Strategy:
    - 1 issue per commit to maximize commit coverage
    - ~50 surviving + ~50 resolved for balanced validation
    - Use the EXACT SAME filtering as the aggregate pipeline (484,606 actionable issues)
    - Stratify by tool proportionally
    - Prefer diverse rule coverage
    """
    # ── Same noise sets as src/reporting/aggregate.py (line 510-526) ──
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

    # Apply same filtering as aggregate pipeline (line 803):
    #   rule not in ALL_NOISE_RULES and not fp_pattern and not issue_is_low_signal
    #
    # Note: ESLint issues in issue_survival.json have rule_id="eslint" (generic),
    # while the actual rule name is only in the message. We try to extract it,
    # and if we can't, we still include them (the aggregate pipeline counts them).
    filtered = []
    for i in all_issues:
        rule = i["rule_id"]
        file_path = i["file_path"]

        # For eslint issues, try to extract the actual rule from message
        # or use "eslint" as-is (the aggregate counts these)
        if i["issue_type"] == "eslint" and rule == "eslint":
            # Try to infer rule from message patterns
            msg = i["message"]
            extracted = _extract_eslint_rule(msg, file_path)
            if extracted:
                rule = extracted
                i["rule_id"] = extracted  # update for display

        # 1. Skip noise rules
        if rule in ALL_NOISE_RULES:
            continue
        # 2. Skip blocked rules
        if rule in BLOCKED_RULES:
            continue
        # 3. Skip low-signal (uses is_issue_low_signal from blocked_rules.py)
        issue_dict = {"rule_id": rule, "symbol": rule, "message": i["message"]}
        if is_issue_low_signal(issue_dict, file_path=file_path):
            continue
        filtered.append(i)

    # Classify language from file extension
    def _lang(fp):
        if fp.endswith(".py"):
            return "python"
        elif fp.endswith((".js", ".jsx")):
            return "javascript"
        elif fp.endswith((".ts", ".tsx")):
            return "typescript"
        return "other"

    py_count = sum(1 for i in filtered if _lang(i["file_path"]) == "python")
    js_count = sum(1 for i in filtered if _lang(i["file_path"]) == "javascript")
    ts_count = sum(1 for i in filtered if _lang(i["file_path"]) == "typescript")
    print(f"    After actionable filtering (same as paper's 484K): {len(filtered):,} issues")
    print(f"      Python: {py_count:,} | JS: {js_count:,} | TS: {ts_count:,}")

    # ── Stratified sampling: by (language_group, survived) ──
    # Mainly focus on Python, include exactly 10 JS/TS samples.
    # Note: ESLint survival data has 0 surviving issues (all resolved in JS/TS),
    # so JS/TS samples will be all resolved, and we balance survived/resolved
    # within Python only.
    PY_TARGET = 90
    JSTS_TARGET = 10

    def _lang_group(fp):
        l = _lang(fp)
        return "python" if l == "python" else "jsts"

    # Group by commit
    by_commit = defaultdict(list)
    for issue in filtered:
        by_commit[issue["commit_sha"]].append(issue)

    # Build pools: (lang_group, survived) → [(sha, issue)]
    pools = defaultdict(list)
    for sha, issues in by_commit.items():
        for issue in issues:
            key = (_lang_group(issue["file_path"]), issue["survived"])
            pools[key].append((sha, issue))

    # Log pool sizes
    for key in sorted(pools.keys()):
        print(f"      Pool {key}: {len(pools[key]):,} issues")

    # Shuffle each pool
    for key in pools:
        random.shuffle(pools[key])

    sampled = []
    used_commits = set()

    # Sample targets: {(lang_group, survived): count}
    # Python: 30 survived + 30 resolved = 60
    # JS/TS: 0 survived (none in data) + 40 resolved = 40
    targets = {
        ("python", True): PY_TARGET // 2,
        ("python", False): PY_TARGET - PY_TARGET // 2,
        ("jsts", True): min(JSTS_TARGET // 2, len(pools.get(("jsts", True), []))),
        ("jsts", False): JSTS_TARGET,
    }
    # If JS/TS survived pool is empty, shift to resolved
    if targets[("jsts", True)] == 0:
        targets[("jsts", False)] = JSTS_TARGET

    for key in sorted(targets.keys()):
        target = targets[key]
        pool = pools.get(key, [])
        picked = 0
        for sha, issue in pool:
            if picked >= target:
                break
            if sha in used_commits:
                continue
            sampled.append(issue)
            used_commits.add(sha)
            picked += 1

    # Fill remaining slots if any group was short
    if len(sampled) < ISSUE_SAMPLES:
        remaining = []
        for key, pool in pools.items():
            for sha, issue in pool:
                if sha not in used_commits:
                    remaining.append(issue)
        random.shuffle(remaining)
        for issue in remaining:
            if len(sampled) >= ISSUE_SAMPLES:
                break
            if issue["commit_sha"] not in used_commits:
                sampled.append(issue)
                used_commits.add(issue["commit_sha"])

    random.shuffle(sampled)
    return sampled


def write_attribution_csv(samples, out_path):
    """Write attribution validation CSV with labeling columns."""
    fieldnames = [
        "id", "ai_tool", "repo", "sha", "url",
        "detection_method", "ai_identifier", "ai_identifier_type",
        "author_name", "author_email", "author_role",
        "message", "date", "stars",
        # Labeling columns
        "label_rater1", "label_rater2", "label_final",
        "notes",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, s in enumerate(samples, 1):
            writer.writerow({
                "id": i,
                "ai_tool": s["ai_tool"],
                "repo": s["repo"],
                "sha": s["sha"],
                "url": s["url"],
                "detection_method": s["detection_method"],
                "ai_identifier": s["ai_identifier"],
                "ai_identifier_type": s["ai_identifier_type"],
                "author_name": s["author_name"],
                "author_email": s["author_email"],
                "author_role": s["author_role"],
                "message": s["message"],
                "date": s["date"],
                "stars": s["stars"],
                "label_rater1": "",
                "label_rater2": "",
                "label_final": "",
                "notes": "",
            })


def write_issue_csv(samples, out_path):
    """Write issue validation CSV with labeling columns.

    Column order is optimized for human review workflow:
    1. Basic identifiers
    2. Issue description (what to look for)
    3. Link to file at commit (click to verify issue)
    4. Survival status + link to file at HEAD (click to verify survival)
    5. Labeling columns
    """
    fieldnames = [
        # ── Identifiers ──
        "id", "ai_tool", "repo",
        # ── Issue description ──
        "rule_id", "severity", "message",
        "file_path", "line",
        # ── Step 1: Verify issue is real (click this link) ──
        "file_at_commit_url",
        "commit_url",
        # ── Step 2: Verify survival at HEAD (click this link) ──
        "survived", "resolved_path", "current_line",
        "file_at_head_url",
        "match_score", "match_reason",
        # ── Labeling ──
        "is_real_issue_rater1", "is_real_issue_rater2", "is_real_issue_final",
        "survival_correct_rater1", "survival_correct_rater2", "survival_correct_final",
        "notes",
        # ── Extra metadata ──
        "commit_sha", "issue_type",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, s in enumerate(samples, 1):
            writer.writerow({
                "id": i,
                "ai_tool": s["ai_tool"],
                "repo": s["repo"],
                "rule_id": s["rule_id"],
                "severity": s["severity"],
                "message": s["message"],
                "file_path": s["file_path"],
                "line": s["line"],
                "file_at_commit_url": s["file_at_commit_url"],
                "commit_url": s["commit_url"],
                "survived": s["survived"],
                "resolved_path": s["resolved_path"],
                "current_line": s["current_line"],
                "file_at_head_url": s["file_at_head_url"],
                "match_score": s["match_score"],
                "match_reason": s["match_reason"],
                "is_real_issue_rater1": "",
                "is_real_issue_rater2": "",
                "is_real_issue_final": "",
                "survival_correct_rater1": "",
                "survival_correct_rater2": "",
                "survival_correct_final": "",
                "notes": "",
                "commit_sha": s["commit_sha"],
                "issue_type": s["issue_type"],
            })


def print_stats(name, samples, key_field):
    """Print distribution stats."""
    dist = defaultdict(int)
    for s in samples:
        dist[s[key_field]] += 1
    print(f"\n  {name} distribution:")
    for k in sorted(dist.keys()):
        print(f"    {k}: {dist[k]}")


def main():
    print("=" * 60)
    print("Validation Sample Preparation")
    print("=" * 60)

    # ── Task 1: AI Attribution Validation ──
    print("\n[1/2] AI Attribution Validation")
    print("  Loading all AI-attributed commits...")
    commits_by_tool = load_all_commits()

    for tool in TOOLS:
        print(f"    {tool}: {len(commits_by_tool[tool]):,} commits")

    print(f"  Sampling {COMMITS_PER_TOOL} per tool ({COMMITS_PER_TOOL * len(TOOLS)} total)...")
    commit_samples = sample_commits(commits_by_tool)
    print(f"  Sampled: {len(commit_samples)} commits")
    print_stats("Tool", commit_samples, "ai_tool")
    print_stats("Detection method", commit_samples, "detection_method")
    print_stats("Author role", commit_samples, "author_role")

    # Write outputs
    out_attr = VAL_DIR / "ai_identifying"
    out_attr.mkdir(parents=True, exist_ok=True)

    csv_path = out_attr / "attribution_sample.csv"
    json_path = out_attr / "attribution_sample.json"

    write_attribution_csv(commit_samples, csv_path)
    with open(json_path, "w") as f:
        json.dump(commit_samples, f, indent=2, ensure_ascii=False)

    print(f"\n  Written: {csv_path}")
    print(f"  Written: {json_path}")

    # ── Task 2: Issue Detection & Survival Validation ──
    print("\n[2/2] Issue Detection & Survival Validation")
    print("  Loading all introduced issues with survival info...")
    all_issues = load_issues_with_survival()
    print(f"  Total issues found: {len(all_issues):,}")

    surv_count = sum(1 for i in all_issues if i["survived"])
    print(f"    Surviving: {surv_count:,}")
    print(f"    Resolved: {len(all_issues) - surv_count:,}")

    print(f"  Sampling {ISSUE_SAMPLES} issues (1 per commit, ~50/50 survived/resolved)...")
    issue_samples = sample_issues(all_issues)
    print(f"  Sampled: {len(issue_samples)} issues")
    print_stats("Tool", issue_samples, "ai_tool")
    print_stats("Issue type", issue_samples, "issue_type")
    print_stats("Survived", issue_samples, "survived")

    # Language distribution
    lang_dist = defaultdict(int)
    for s in issue_samples:
        fp = s["file_path"]
        if fp.endswith(".py"):
            lang_dist["python"] += 1
        elif fp.endswith((".js", ".jsx")):
            lang_dist["javascript"] += 1
        elif fp.endswith((".ts", ".tsx")):
            lang_dist["typescript"] += 1
        else:
            lang_dist["other"] += 1
    print(f"\n  Language distribution:")
    for k in sorted(lang_dist):
        print(f"    {k}: {lang_dist[k]}")

    print_stats("Rule", issue_samples, "rule_id")

    # Write outputs
    out_issue = VAL_DIR / "vul_check"
    out_issue.mkdir(parents=True, exist_ok=True)

    csv_path = out_issue / "issue_sample.csv"
    json_path = out_issue / "issue_sample.json"

    write_issue_csv(issue_samples, csv_path)
    with open(json_path, "w") as f:
        json.dump(issue_samples, f, indent=2, ensure_ascii=False)

    print(f"\n  Written: {csv_path}")
    print(f"  Written: {json_path}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("Validation files ready!")
    print("=" * 60)
    print(f"""
Next steps:
  1. AI Attribution (data/validation/ai_identifying/attribution_sample.csv):
     - Two raters independently label each row:
       label_rater1/label_rater2 = 'correct' | 'incorrect' | 'uncertain'
     - Resolve disagreements → label_final
     - Compute Cohen's kappa and precision

  2. Issue Detection (data/validation/vul_check/issue_sample.csv):
     - Two raters independently label each row:
       is_real_issue = 'yes' | 'no' | 'uncertain'
       survival_correct = 'yes' | 'no' | 'uncertain'
     - For each issue, open the commit_url and check the code
     - For survival, check the file at HEAD
     - Compute Cohen's kappa, precision, accuracy
""")


if __name__ == "__main__":
    main()
