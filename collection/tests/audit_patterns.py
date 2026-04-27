#!/usr/bin/env python3
"""
Comprehensive audit of AI detection patterns.
Tests for false positives and ensures all patterns are accurate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.tools import AI_TOOLS
from config.actors import AI_ACTORS


def audit_patterns():
    """Audit all patterns for potential false positive issues."""
    
    issues = []
    
    # === Rules for safe patterns ===
    # 1. author_name should end with [bot], AI, or be very specific
    # 2. author_email_like should have specific domain, not just partial word match
    # 3. Short common words are risky: v0, bolt, cline, cody, devin, sweep, etc.
    
    RISKY_NAMES = [
        "devin", "Devin",        # Common person name
        "cody", "Cody",          # Common person name
        "bolt",                   # Common word
        "v0",                     # Matches v0idpwn, etc.
        "cline", "Cline",        # Nickname for Caroline
        "pieces",                 # Common word
        "gitpod", "Gitpod",      # Could match employees
        "continue", "Continue",   # Common word
        "sweep", "Sweep",        # Common word
        "codex", "Codex",        # Common word
        "claude",                 # Could match person (rare)
        "cursor", "Cursor",      # Could match employee
        "replit", "Replit",      # Could match employee
        "lovable", "Lovable",    # Common word
        "tabnine", "Tabnine",    # Could match employee
        "codeium", "Codeium",    # Could match employee
        "windsurf", "Windsurf",  # Common word
        "phind", "Phind",        # Could match username
        "supermaven",            # Common-ish
    ]
    
    SAFE_SUFFIXES = ["[bot]", " AI", "-ai", "-bot", " Agent", " Dev",
                     " Autofix powered by AI"]
    
    print("=" * 80)
    print("COMPREHENSIVE AI DETECTION PATTERN AUDIT")
    print("=" * 80)
    
    # Check tools.py patterns
    print("\nAuditing tools.py patterns...\n")
    
    for tool_id, config in AI_TOOLS.items():
        patterns = config.get("patterns", {})
        
        # Check author_name patterns
        for name in patterns.get("author_name", []):
            is_safe = any(name.endswith(suffix) for suffix in SAFE_SUFFIXES)
            is_risky = name.lower() in [r.lower() for r in RISKY_NAMES]
            
            if is_risky and not is_safe:
                issues.append({
                    "file": "tools.py",
                    "tool": tool_id,
                    "pattern_type": "author_name",
                    "pattern": name,
                    "issue": f"RISKY: '{name}' is a common name/word without safe suffix",
                    "severity": "high" if name.lower() in ["devin", "cody"] else "medium",
                })
            elif not is_safe and len(name) < 6:
                issues.append({
                    "file": "tools.py",
                    "tool": tool_id,
                    "pattern_type": "author_name",
                    "pattern": name,
                    "issue": f"WARNING: Short pattern '{name}' without safe suffix",
                    "severity": "low",
                })
        
        # Check author_email_like patterns
        for email in patterns.get("author_email_like", []):
            # Check for overly broad patterns
            if email.count("%") >= 2 and "@" not in email:
                issues.append({
                    "file": "tools.py",
                    "tool": tool_id,
                    "pattern_type": "author_email_like",
                    "pattern": email,
                    "issue": f"RISKY: Broad pattern '{email}' (no @ domain restriction)",
                    "severity": "high",
                })
    
    # Check actors.py patterns
    print("Auditing actors.py patterns...\n")
    
    for tool_id, config in AI_ACTORS.items():
        for actor in config.get("actors", []):
            if not actor.endswith("[bot]"):
                issues.append({
                    "file": "actors.py",
                    "tool": tool_id,
                    "pattern_type": "actors",
                    "pattern": actor,
                    "issue": f"WARNING: Actor '{actor}' doesn't end with [bot]",
                    "severity": "low",
                })
    
    # Print issues by severity
    if issues:
        for severity in ["high", "medium", "low"]:
            severity_issues = [i for i in issues if i.get("severity") == severity]
            if not severity_issues:
                continue
            print(f"\n{'!!' if severity == 'high' else '!'} {severity.upper()} severity ({len(severity_issues)}):")
            print("-" * 80)
            for issue in severity_issues:
                print(f"  [{issue['tool']}] {issue['pattern_type']}: {issue['pattern']}")
                print(f"      -> {issue['issue']}")
        
        print(f"\nTotal: {len(issues)} issues found")
    else:
        print("All patterns look safe!")
    
    return issues


def test_false_positives():
    """Test known false positive cases."""
    from detection.scanner import detect_ai_commit
    
    print("\n" + "=" * 80)
    print("FALSE POSITIVE TESTS")
    print("=" * 80 + "\n")
    
    # These should ALL return None (not AI)
    false_positives = [
        # Person names
        ("Devin Weaver", "suki@tritarget.org", "", "Person named Devin"),
        ("Devin Gaffney", "itsme@devingaffney.com", "", "Person named Devin (2)"),
        ("Cody Kociemba", "cody@symbaventures.com", "", "Person named Cody"),
        ("Cody Stamps", "cody.stamps@hey.com", "", "Person named Cody (2)"),
        ("Christophe Bornet", "cbornet@hotmail.com", "", "Regular person"),
        
        # Internal/misconfigured domains containing "blackbox"
        ("Uglješa Erceg", "uerceg@blackbox.lan", "", "Internal LAN domain"),
        ("Finn Herpich", "finn@blackbox.(none)", "", "Misconfigured git config"),
        
        # Usernames that look like AI
        ("v0idpwn", "v0idpwn@gmail.com", "", "Username starts with v0"),
        ("xs5871", "60395129+xs5871@users.noreply.github.com", "", "Random username"),
        ("SeanCline", "sean@company.com", "", "Person with Cline in name"),
        
        # Co-author lines with person names
        ("Human Dev", "dev@company.com", "Co-authored-by: Devin Weaver <devin@company.com>", "Coauthor Devin"),
        ("Human Dev", "dev@company.com", "Co-authored-by: Cody Smith <cody@company.com>", "Coauthor Cody"),
        ("Human Dev", "dev@company.com", "Co-authored-by: v0idpwn <v0idpwn@gmail.com>", "Coauthor v0idpwn"),
    ]
    
    passed = 0
    failed = 0
    
    for name, email, message, description in false_positives:
        result = detect_ai_commit(name, email, message)
        if result is None:
            print(f"  PASS: {description} (not detected)")
            passed += 1
        else:
            print(f"  FAIL: {description} (detected as {result['tool_key']})")
            failed += 1
    
    print(f"\nFalse positive tests: {passed} passed, {failed} failed")
    return failed == 0


def test_true_positives():
    """Test that actual AI commits are detected."""
    from detection.scanner import detect_ai_commit
    
    print("\n" + "=" * 80)
    print("TRUE POSITIVE TESTS")
    print("=" * 80 + "\n")
    
    # These should ALL be detected as AI
    true_positives = [
        ("Claude", "noreply@anthropic.com", "", "claude", "Claude commit"),
        ("Copilot", "Copilot@users.noreply.github.com", "", "copilot", "Copilot commit"),
        ("cursoragent", "cursoragent@cursor.com", "", "cursor", "Cursor commit"),
        ("aider", "noreply@aider.chat", "", "aider", "Aider via email"),
        ("Human", "human@gmail.com", "Co-authored-by: aider (gpt-4) <noreply@aider.chat>", "aider", "Aider coauthor"),
        ("Human", "human@gmail.com", "Co-authored-by: Claude <noreply@anthropic.com>", "claude", "Claude coauthor"),
        ("Human", "human@gmail.com", "Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>", "copilot", "Copilot coauthor"),
    ]
    
    passed = 0
    failed = 0
    
    for name, email, message, expected_tool, description in true_positives:
        result = detect_ai_commit(name, email, message)
        actual_tool = result["tool_key"] if result else None
        if actual_tool == expected_tool:
            print(f"  PASS: {description} -> {actual_tool}")
            passed += 1
        else:
            print(f"  FAIL: {description} (expected {expected_tool}, got {actual_tool})")
            failed += 1
    
    print(f"\nTrue positive tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    issues = audit_patterns()
    fp_ok = test_false_positives()
    tp_ok = test_true_positives()
    
    print("\n" + "=" * 80)
    print("OVERALL RESULTS")
    print("=" * 80)
    print(f"Pattern audit issues: {len(issues)}")
    print(f"False positive tests: {'PASS' if fp_ok else 'FAIL'}")
    print(f"True positive tests:  {'PASS' if tp_ok else 'FAIL'}")
    print("=" * 80)
    
    if not fp_ok or not tp_ok:
        sys.exit(1)
