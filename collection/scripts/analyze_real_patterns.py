#!/usr/bin/env python3
"""
Analyze REAL commit data to find actual email/name patterns per AI agent.

Reads commit-level JSON files from collect-commits results and extracts
the actual author_name, author_email, and ai_identifier patterns used.

This helps us:
1. Verify our patterns match real data
2. Find common email patterns we might be missing
3. Identify which agents need email-only vs name-only detection
"""
import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

# Path to existing commit results
COMMIT_RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "history" / "collect-commits" / "result"


def load_all_commits(results_dir: Path, max_per_file: int = None):
    """Load all AI commits from result JSON files."""
    all_commits = []
    
    json_files = sorted(results_dir.glob("*_commits.json"))
    print(f"Found {len(json_files)} commit result files")
    
    for jf in json_files:
        try:
            data = json.load(open(jf, "r", encoding="utf-8"))
            commits = data.get("ai_commits", [])
            if max_per_file:
                commits = commits[:max_per_file]
            for c in commits:
                c["_source_file"] = jf.name
            all_commits.extend(commits)
        except Exception as e:
            print(f"  Error reading {jf.name}: {e}")
    
    print(f"Loaded {len(all_commits)} AI commits total")
    return all_commits


def analyze_patterns(commits):
    """Analyze email/name patterns grouped by ai_tool."""
    # Group commits by detected tool
    by_tool = defaultdict(list)
    for c in commits:
        tool = c.get("ai_tool", "unknown")
        by_tool[tool].append(c)
    
    print("\n" + "=" * 80)
    print("REAL COMMIT PATTERNS BY AI TOOL")
    print("=" * 80)
    
    for tool in sorted(by_tool.keys()):
        commits_for_tool = by_tool[tool]
        
        # Collect unique patterns
        author_names = Counter()
        author_emails = Counter()
        detection_methods = Counter()
        ai_identifiers = Counter()
        ai_id_types = Counter()
        
        for c in commits_for_tool:
            author_names[c.get("author_name", "")] += 1
            author_emails[c.get("author_email", "")] += 1
            detection_methods[c.get("detection_method", "")] += 1
            if c.get("ai_identifier"):
                ai_identifiers[c["ai_identifier"]] += 1
            if c.get("ai_identifier_type"):
                ai_id_types[c["ai_identifier_type"]] += 1
        
        # Extract email domains
        email_domains = Counter()
        for email, count in author_emails.items():
            if "@" in email:
                domain = email.split("@", 1)[1].lower()
                email_domains[domain] += count
        
        print(f"\n{'─' * 80}")
        print(f"  {tool.upper()} ({len(commits_for_tool)} commits)")
        print(f"{'─' * 80}")
        
        print(f"\n  Detection methods:")
        for method, cnt in detection_methods.most_common():
            print(f"    {method}: {cnt}")
        
        print(f"\n  Author names (top 10):")
        for name, cnt in author_names.most_common(10):
            print(f"    \"{name}\": {cnt}")
        
        print(f"\n  Author emails (top 10):")
        for email, cnt in author_emails.most_common(10):
            print(f"    {email}: {cnt}")
        
        print(f"\n  Email domains:")
        for domain, cnt in email_domains.most_common(10):
            print(f"    @{domain}: {cnt}")
        
        if ai_identifiers:
            print(f"\n  AI identifiers matched:")
            for ident, cnt in ai_identifiers.most_common(10):
                print(f"    {ident}: {cnt}")
    
    return by_tool


def suggest_improvements(by_tool):
    """Suggest pattern improvements based on real data."""
    print("\n" + "=" * 80)
    print("SUGGESTED PATTERN IMPROVEMENTS")
    print("=" * 80)
    
    # Load current patterns for comparison
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config.tools import AI_TOOLS
    
    for tool, commits in sorted(by_tool.items()):
        current = AI_TOOLS.get(tool, {}).get("patterns", {})
        current_emails = set(current.get("author_email", []))
        current_email_likes = set(current.get("author_email_like", []))
        current_names = set(current.get("author_name", []))
        
        # Find email patterns from real data
        real_emails = Counter()
        real_names = Counter()
        for c in commits:
            email = c.get("author_email", "")
            name = c.get("author_name", "")
            if email:
                real_emails[email.lower()] += 1
            if name:
                real_names[name] += 1
        
        # Find emails NOT covered by current patterns
        import re
        uncovered_emails = {}
        for email, cnt in real_emails.most_common():
            covered = False
            # Check exact match
            for pat in current_emails:
                if pat.lower() in email:
                    covered = True
                    break
            # Check LIKE patterns
            if not covered:
                for pat in current_email_likes:
                    regex = pat.replace("%", ".*").lower()
                    if re.search(regex, email):
                        covered = True
                        break
            if not covered and cnt >= 2:
                uncovered_emails[email] = cnt
        
        if uncovered_emails:
            print(f"\n  [{tool}] Uncovered email patterns (>= 2 commits):")
            for email, cnt in sorted(uncovered_emails.items(), key=lambda x: -x[1]):
                print(f"    {email} ({cnt} commits)")


def main():
    results_dir = COMMIT_RESULTS_DIR
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        sys.exit(1)
    
    commits = load_all_commits(results_dir)
    by_tool = analyze_patterns(commits)
    suggest_improvements(by_tool)


if __name__ == "__main__":
    main()
