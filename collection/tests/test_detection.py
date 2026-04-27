#!/usr/bin/env python3
"""
Test script to verify detection patterns against known commits.

Adapted for the new Dict return type from scanner.detect_ai_commit().
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from detection.scanner import detect_ai_commit, detect_ai_from_author, detect_ai_from_coauthor


# Test cases: (description, author_name, author_email, message, actor_login, expected_tool)
TEST_CASES = [
    # === Aider coauthor cases ===
    (
        "Aider via Co-authored-by (gemini model)",
        "github-actions[bot]",
        "41898282+github-actions[bot]@users.noreply.github.com",
        "chore: Clean up impactMetrics\nCo-authored-by: aider (gemini/gemini-2.5-pro) <aider@aider.chat>",
        "",
        "aider",
    ),
    (
        "Aider via Co-authored-by (azure model)",
        "potatoqualitee",
        "potatoqualitee@users.noreply.github.com",
        "style: align hashtable properties\nCo-authored-by: aider (azure/gpt-4o-mini) <aider@aider.chat>",
        "",
        "aider",
    ),
    
    # === Lovable bot variants ===
    (
        "Lovable bot (lovable-dev) as author",
        "lovable-dev[bot]",
        "lovable-dev[bot]@users.noreply.github.com",
        "Changes",
        "",
        "lovable",
    ),
    (
        "Lovable bot (gpt-engineer-app) as author",
        "gpt-engineer-app[bot]",
        "gpt-engineer-app[bot]@users.noreply.github.com",
        "feat: add feature",
        "",
        "lovable",
    ),
    
    # === Claude coauthor ===
    (
        "Claude via Co-Authored-By",
        "bl4ckmeow",
        "bl4ckf1r3_meow@proton.me",
        "feat: Add flood layer toggle\nCo-Authored-By: Claude <noreply@anthropic.com>",
        "",
        "claude",
    ),
    
    # === Claude as author ===
    (
        "Claude as commit author",
        "Claude",
        "noreply@anthropic.com",
        "fix: update config",
        "",
        "claude",
    ),
    
    # === Copilot coauthor ===
    (
        "Copilot via Co-authored-by",
        "Thomas Heartman",
        "thomas@getunleash.io",
        "chore: replace flags\nCo-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>",
        "",
        "copilot",
    ),
    
    # === Copilot as author ===
    (
        "Copilot as commit author",
        "Copilot",
        "198982749+Copilot@users.noreply.github.com",
        "Fix docs link 404s",
        "",
        "copilot",
    ),
    
    # === Copilot via actor.login ===
    (
        "Copilot via actor login",
        "Some Human",
        "human@example.com",
        "feat: add feature",
        "Copilot",
        "copilot",
    ),
    
    # === Gemini code assist ===
    (
        "Gemini Code Assist bot as author",
        "gemini-code-assist[bot]",
        "gemini-code-assist[bot]@users.noreply.github.com",
        "feat: add new feature",
        "",
        "gemini",
    ),
    
    # === Devin bot ===
    (
        "Devin bot as author",
        "devin-ai-integration[bot]",
        "devin-ai-integration[bot]@users.noreply.github.com",
        "fix: bug fix",
        "",
        "devin",
    ),
    
    # === CodeRabbit bot ===
    (
        "CodeRabbit bot as author",
        "coderabbitai[bot]",
        "coderabbitai[bot]@users.noreply.github.com",
        "chore: update dependencies",
        "",
        "coderabbit",
    ),
    
    # === Bolt/StackBlitz ===
    (
        "Bolt StackBlitz bot as author",
        "bolt-new-by-stackblitz[bot]",
        "bolt-new-by-stackblitz[bot]@users.noreply.github.com",
        "feat: initial commit",
        "",
        "bolt",
    ),
    
    # === Cursor agent ===
    (
        "Cursor agent as author",
        "cursoragent",
        "cursoragent@cursor.com",
        "feat: add new feature",
        "",
        "cursor",
    ),
    
    # === Cursor via actor.login ===
    (
        "Cursor via actor login",
        "Some Human",
        "human@example.com",
        "feat: add feature",
        "cursor[bot]",
        "cursor",
    ),
    
    # === Aider as commit author ===
    (
        "Aider as commit author via email",
        "aider",
        "noreply@aider.chat",
        "refactor: extract helper",
        "",
        "aider",
    ),
    
    # =============================================
    # Should NOT match - regular human commits
    # =============================================
    (
        "Regular human commit (should not match)",
        "Finn Herpich",
        "finn@example.com",
        "Bugfix: fix December cron issue",
        "",
        None,
    ),
    (
        "v01dXYZ (NOT v0 by Vercel, should not match)",
        "v01dXYZ",
        "v01dxyz@users.noreply.github.com",
        "[X86AsmParser] fix\nCo-authored-by: v01dxyz <v01dxyz@v01d.xyz>",
        "",
        None,
    ),
    (
        "Person named Devin (should not match)",
        "Devin Weaver",
        "suki@tritarget.org",
        "fix: update readme",
        "",
        None,
    ),
    (
        "Person named Cody (should not match)",
        "Cody Kociemba",
        "cody@symbaventures.com",
        "feat: add settings page",
        "",
        None,
    ),
    (
        "Internal blackbox LAN domain (should not match)",
        "Uglješa Erceg",
        "uerceg@blackbox.lan",
        "fix: network config",
        "",
        None,
    ),
    (
        "Misconfigured git config blackbox.(none) (should not match)",
        "Finn Herpich",
        "finn@blackbox.(none)",
        "chore: cleanup",
        "",
        None,
    ),
    (
        "SeanCline (should not match Cline AI)",
        "SeanCline",
        "sean@company.com",
        "fix: button alignment",
        "",
        None,
    ),
    (
        "Coauthor Devin Weaver (should not match)",
        "Human Dev",
        "dev@company.com",
        "fix: stuff\nCo-authored-by: Devin Weaver <devin@company.com>",
        "",
        None,
    ),
    (
        "Coauthor Cody Smith (should not match)",
        "Human Dev",
        "dev@company.com",
        "fix: stuff\nCo-authored-by: Cody Smith <cody@company.com>",
        "",
        None,
    ),
]


def run_tests():
    print("=" * 70)
    print("AI COMMIT DETECTION TESTS")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for description, author_name, author_email, message, actor_login, expected in TEST_CASES:
        result = detect_ai_commit(
            author_name=author_name,
            author_email=author_email,
            commit_message=message,
            actor_login=actor_login,
        )
        
        # New return type is Dict or None
        actual_tool = result["tool_key"] if result else None
        
        if actual_tool == expected:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1
        
        print(f"\n{'✅' if status == 'PASS' else '❌'} {status}: {description}")
        if actual_tool != expected:
            print(f"  Author: {author_name} <{author_email}>")
            if actor_login:
                print(f"  Actor: {actor_login}")
            print(f"  Expected: {expected}")
            print(f"  Got: {result}")
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 70)
    
    return failed == 0


def test_author_role():
    """Test that author_role is correctly set."""
    print("\n" + "=" * 70)
    print("AUTHOR ROLE TESTS")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    cases = [
        # (description, args, expected_role)
        (
            "AI is the commit author -> sole_author",
            {"author_name": "Claude", "author_email": "noreply@anthropic.com"},
            "sole_author",
        ),
        (
            "AI pushed via actor.login -> sole_author",
            {"author_name": "Human", "author_email": "human@example.com", "actor_login": "Copilot"},
            "sole_author",
        ),
        (
            "AI is co-author -> coauthor",
            {"author_name": "Human", "author_email": "human@example.com",
             "commit_message": "fix\nCo-authored-by: Claude <noreply@anthropic.com>"},
            "coauthor",
        ),
    ]
    
    for description, kwargs, expected_role in cases:
        result = detect_ai_commit(**kwargs)
        actual_role = result.get("author_role") if result else None
        
        if actual_role == expected_role:
            print(f"\n✅ PASS: {description}")
            passed += 1
        else:
            print(f"\n❌ FAIL: {description}")
            print(f"  Expected role: {expected_role}, Got: {actual_role}")
            failed += 1
    
    print(f"\nROLE TESTS: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success1 = run_tests()
    success2 = test_author_role()
    
    print("\n" + "=" * 70)
    print("OVERALL:", "ALL PASSED" if (success1 and success2) else "SOME FAILED")
    print("=" * 70)
    
    sys.exit(0 if (success1 and success2) else 1)
