"""
Python-specific analysis tool runners (pylint, bandit, radon, cognitive complexity).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.utils.tools.common import run_tool, RULE_SEVERITY_OVERRIDES, PYLINT_DISABLED_SYMBOLS


def run_pylint(temp_path: Path, detailed: bool = False) -> Union[
    Tuple[Optional[float], int, int],
    Tuple[Optional[float], int, int, List[Dict[str, Any]]]
]:
    """
    Run pylint and return score, errors, warnings.

    Args:
        temp_path: Path to Python file to analyze
        detailed: If True, also return list of raw messages

    Returns:
        If detailed=False: (score, errors, warnings)
        If detailed=True: (score, errors, warnings, messages)
    """
    score = None
    errors = 0
    warnings = 0
    raw_messages: List[Dict[str, Any]] = []

    # Run with JSON output for messages (includes score in stats)
    returncode, stdout, _ = run_tool(
        [
            "pylint",
            "--output-format=json2",
            # Reduce false positives due to missing dependency context.
            # NOTE: This does NOT prevent other meaningful error/warning signals.
            "--disable=" + ",".join(sorted(PYLINT_DISABLED_SYMBOLS)),
            str(temp_path),
        ]
    )

    if returncode >= 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            messages = data.get("messages", [])
            statistics = data.get("statistics", {})

            # Get score from statistics
            score = statistics.get("score")

            # Filter out environment-dependent messages (imports without deps installed)
            filtered_messages = [
                m for m in messages
                if (m.get("symbol") or "") not in PYLINT_DISABLED_SYMBOLS
            ]

            for item in filtered_messages:
                msg_type = item.get("type")
                if msg_type in {"error", "fatal"}:
                    errors += 1
                elif msg_type == "warning":
                    warnings += 1

                if detailed:
                    raw_messages.append({
                        "line": item.get("line"),
                        "column": item.get("column"),
                        "type": msg_type,
                        "symbol": item.get("symbol"),
                        "message": item.get("message"),
                    })
        except json.JSONDecodeError:
            pass

    if detailed:
        return score, errors, warnings, raw_messages
    return score, errors, warnings


def run_radon_cc(temp_path: Path) -> Optional[float]:
    """Run radon cyclomatic complexity."""
    returncode, stdout, _ = run_tool(["radon", "cc", "-j", str(temp_path)])
    if returncode != 0 or not stdout.strip():
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    blocks = data.get(str(temp_path))
    if not blocks:
        return 0.0
    total = 0.0
    for block in blocks:
        total += block.get("complexity", 0)
    return total


def run_radon_mi(temp_path: Path) -> Optional[float]:
    """Run radon maintainability index."""
    returncode, stdout, _ = run_tool(["radon", "mi", "-j", str(temp_path)])
    if returncode != 0 or not stdout.strip():
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    result = data.get(str(temp_path))
    if not result:
        return None
    return result.get("mi")


def run_bandit(temp_path: Path, detailed: bool = False, blocked_rules: set = None) -> Union[
    Tuple[int, int, int],  # (high, medium, low) severity counts
    Tuple[int, int, int, List[Dict[str, Any]]]  # with details
]:
    """
    Run bandit security scanner on Python files.

    Returns:
        If detailed=False: (high_count, medium_count, low_count)
        If detailed=True: (high, medium, low, list of issue details)
    """
    returncode, stdout, _ = run_tool([
        "bandit", "-f", "json", "-q", str(temp_path)
    ])

    # Bandit returns 1 if issues found, 0 if clean
    if returncode < 0:  # Tool not found
        return (0, 0, 0, []) if detailed else (0, 0, 0)

    try:
        data = json.loads(stdout) if stdout.strip() else {"results": []}
    except json.JSONDecodeError:
        return (0, 0, 0, []) if detailed else (0, 0, 0)

    results = data.get("results", [])

    # Filter out blocked rules
    if blocked_rules:
        results = [r for r in results if r.get("test_id") not in blocked_rules]

    high = sum(1 for r in results if r.get("issue_severity") == "HIGH")
    medium = sum(1 for r in results if r.get("issue_severity") == "MEDIUM")
    low = sum(1 for r in results if r.get("issue_severity") == "LOW")

    if detailed:
        issues = []
        for r in results:
            rule_id = r.get("test_id")
            severity = r.get("issue_severity", "UNKNOWN").upper()

            # Apply severity overrides
            if rule_id in RULE_SEVERITY_OVERRIDES:
                severity = RULE_SEVERITY_OVERRIDES[rule_id].upper()

            issues.append({
                "line": r.get("line_number"),
                "severity": severity.lower(),
                "confidence": r.get("issue_confidence", "UNKNOWN").lower(),
                "rule": rule_id,
                "message": r.get("issue_text"),
                "type": "security",
            })
        return high, medium, low, issues

    return high, medium, low


def run_cognitive_complexity(temp_path: Path) -> int:
    """
    Estimate cognitive complexity based on code structure.

    Cognitive complexity (per SonarQube) measures code understandability
    by penalizing:
    - Nested control flow (exponentially)
    - Breaks in linear flow (continue, break, goto)
    - Recursion

    This is an approximation since true cognitive complexity requires AST.
    """
    try:
        content = temp_path.read_text()
    except Exception:
        return 0

    lines = content.splitlines()
    complexity = 0
    nesting = 0

    # Patterns that increase nesting
    nesting_keywords = re.compile(
        r'\b(if|elif|else|for|while|try|except|with|match|case)\b.*:$'
    )
    # Patterns that break linear flow
    break_flow = re.compile(r'\b(break|continue|return|raise|yield)\b')
    # Lambda/comprehension nesting
    nested_expr = re.compile(r'\[.+for.+in.+\]|\{.+for.+in.+\}')
    # Recursion detection (function calls itself - simplified)
    func_def = re.compile(r'^\s*def\s+(\w+)')

    current_func = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Track current function for recursion detection
        func_match = func_def.match(line)
        if func_match:
            current_func = func_match.group(1)
            nesting = 0  # Reset nesting for new function

        # Check for nesting keywords
        if nesting_keywords.search(stripped):
            complexity += (1 + nesting)  # Nested structures cost more
            nesting += 1

        # Check for flow breakers
        if break_flow.search(stripped):
            complexity += 1

        # Check for nested expressions (list/dict comprehensions)
        if nested_expr.search(stripped):
            complexity += 2  # Comprehensions add complexity

        # Simple recursion check
        if current_func and re.search(rf'\b{current_func}\s*\(', stripped):
            if not func_def.match(line):  # Not the definition itself
                complexity += 3  # Recursion penalty

        # Decrease nesting on dedent (simplified)
        indent = len(line) - len(line.lstrip())
        # This is a simplification - proper implementation needs AST

    return complexity
