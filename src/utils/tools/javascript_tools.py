"""
JavaScript/TypeScript analysis tool runners (eslint, njsscan, jscpd).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from src.utils.tools.common import run_tool, RULE_SEVERITY_OVERRIDES


# Path to packaged ESLint config
ESLINT_CONFIG = Path(__file__).parent.parent.parent / "config" / "eslint.config.mjs"


def run_eslint(temp_path: Path, detailed: bool = False, blocked_rules: set = None) -> Union[
    Tuple[int, int],
    Tuple[int, int, List[Dict[str, Any]]]
]:
    """
    Run eslint and return error/warning counts.

    Args:
        temp_path: Path to JS/TS file to analyze
        detailed: If True, also return list of raw messages

    Returns:
        If detailed=False: (errors, warnings)
        If detailed=True: (errors, warnings, messages)
    """
    import shutil
    import tempfile

    # ESLint v9 needs config file in same directory as source
    # Copy file to temp dir with our config
    work_dir = Path(tempfile.mkdtemp())
    try:
        # Copy the source file
        target_file = work_dir / temp_path.name
        shutil.copy(temp_path, target_file)

        # Copy our ESLint config
        if ESLINT_CONFIG.exists():
            shutil.copy(ESLINT_CONFIG, work_dir / "eslint.config.mjs")

        # Symlink node_modules into work dir so ESM imports work.
        # Check multiple locations: env var (Docker), project root, global npm.
        node_modules = None
        candidates = []
        env_nm = os.environ.get("ESLINT_NODE_MODULES", "")
        if env_nm:
            candidates.append(Path(env_nm))
        candidates.append(Path(__file__).parent.parent.parent.parent / "node_modules")
        for candidate in candidates:
            if candidate.is_dir():
                node_modules = candidate
                break
        if node_modules is None:
            # Fallback: global npm root (e.g. /usr/lib/node_modules)
            from src.utils.tools.common import run_tool as _rt
            rc, out, _ = _rt(["npm", "root", "-g"], timeout=10)
            if rc == 0 and out.strip():
                g = Path(out.strip())
                if g.is_dir():
                    node_modules = g
        if node_modules is not None:
            (work_dir / "node_modules").symlink_to(node_modules.resolve())

        returncode, stdout, stderr = run_tool(
            [
                "eslint",
                "--format=json",
                "--no-warn-ignored",
                target_file.name  # Use relative path
            ],
            cwd=work_dir  # Run from work dir so config is found
        )
    finally:
        # Cleanup
        shutil.rmtree(work_dir, ignore_errors=True)

    if returncode < 0 or (returncode != 0 and not stdout.strip()):
        return (0, 0, []) if detailed else (0, 0)
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return (0, 0, []) if detailed else (0, 0)
    if not data:
        return (0, 0, []) if detailed else (0, 0)

    entry = data[0]
    messages = entry.get("messages", [])

    # Filter out false positives from parsing/config issues
    # These are not real code quality issues, just ESLint config limitations
    def is_false_positive(msg):
        message = msg.get("message", "")
        rule_id = msg.get("ruleId")

        # No rule ID = parsing error, not a lint rule
        if rule_id is None:
            return True

        # Parsing errors (TypeScript, JSX, Flow, decorators, etc.)
        if message.startswith("Parsing error"):
            return True

        # Only skip genuine ESLint infrastructure problems, NOT real findings
        skip_messages = [
            "Cannot find module",         # Module resolution (not installed)
            "Unable to resolve path",     # Import resolution
            "Definition for rule",        # Missing ESLint plugin
            "Failed to load plugin",      # Missing ESLint plugin
            "Cannot read config file",    # Config issues
        ]

        for skip in skip_messages:
            if skip in message:
                return True

        # Skip rules that require full project context
        skip_rules = [
            "import/",           # Import plugin needs full project
            "node/",             # Node rules need package.json
            "react/",            # React rules need React context
        ]

        for skip in skip_rules:
            if rule_id and rule_id.startswith(skip):
                return True

        return False

    filtered_messages = [msg for msg in messages if not is_false_positive(msg)]

    # Filter out blocked rules (e.g., no-console, curly)
    if blocked_rules:
        filtered_messages = [msg for msg in filtered_messages if msg.get("ruleId") not in blocked_rules]

    errors = sum(1 for msg in filtered_messages if msg.get("severity") == 2)
    warnings = sum(1 for msg in filtered_messages if msg.get("severity") == 1)

    if detailed:
        raw_messages = []
        for msg in filtered_messages:
            raw_messages.append({
                "line": msg.get("line"),
                "column": msg.get("column"),
                "severity": "error" if msg.get("severity") == 2 else "warning",
                "rule": msg.get("ruleId"),
                "message": msg.get("message"),
            })
        return errors, warnings, raw_messages

    return errors, warnings


def run_njsscan(temp_path: Path, detailed: bool = False) -> Union[
    Tuple[int, int, int],  # (high, medium, low) severity counts
    Tuple[int, int, int, List[Dict[str, Any]]]  # with details
]:
    """
    Run njsscan security scanner on JavaScript/TypeScript/HTML files.

    Uses semgrep rules to detect security issues in JS code.

    Returns:
        If detailed=False: (high_count, medium_count, low_count)
        If detailed=True: (high, medium, low, list of issue details)
    """
    import shutil
    import tempfile

    # njsscan requires a directory, not a single file
    # Create temp dir with the file
    work_dir = Path(tempfile.mkdtemp())
    try:
        target_file = work_dir / temp_path.name
        shutil.copy(temp_path, target_file)

        returncode, stdout, stderr = run_tool([
            "njsscan", "--json", str(work_dir)
        ])

        if returncode < 0:  # Tool not found
            return (0, 0, 0, []) if detailed else (0, 0, 0)

        try:
            # njsscan output may have logs before JSON
            # Find the JSON part
            json_start = stdout.find('{')
            if json_start == -1:
                return (0, 0, 0, []) if detailed else (0, 0, 0)
            data = json.loads(stdout[json_start:])
        except json.JSONDecodeError:
            return (0, 0, 0, []) if detailed else (0, 0, 0)

        # Count by severity
        high = 0
        medium = 0
        low = 0
        issues = []

        # njsscan groups issues by rule
        for rule_id, findings in data.get("nodejs", {}).items():
            # Check for severity override
            severity_override = RULE_SEVERITY_OVERRIDES.get(rule_id)
            base_severity = findings.get("metadata", {}).get("severity", "WARNING").upper()
            severity = severity_override.upper() if severity_override else base_severity

            for finding in findings.get("files", []):

                if severity in ("ERROR", "HIGH", "CRITICAL"):
                    high += len(finding.get("match_lines", []) or [1])
                elif severity in ("WARNING", "MEDIUM"):
                    medium += len(finding.get("match_lines", []) or [1])
                else:
                    low += len(finding.get("match_lines", []) or [1])

                if detailed:
                    lines = finding.get("match_lines", [])
                    line = lines[0] if lines else 0
                    issues.append({
                        "line": line,
                        "severity": severity.lower(),
                        "rule": rule_id,
                        "message": findings.get("metadata", {}).get("description", "Security issue detected"),
                        "type": "security",
                    })

        if detailed:
            return high, medium, low, issues
        return high, medium, low

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def run_jscpd(temp_path: Path, detailed: bool = False) -> Union[
    int,
    Tuple[int, List[Dict[str, Any]]]
]:
    """
    Run jscpd (copy/paste detector) and return duplicate count.

    Args:
        temp_path: Path to file to analyze
        detailed: If True, return list of duplicate blocks

    Returns:
        If detailed=False: int count of duplicates
        If detailed=True: (count, list of duplicate details)
    """
    import shutil
    import tempfile

    # jscpd needs a directory, so copy file to temp dir
    work_dir = Path(tempfile.mkdtemp())
    try:
        target_file = work_dir / temp_path.name
        shutil.copy(temp_path, target_file)

        returncode, stdout, stderr = run_tool([
            "jscpd",
            "--format", "json",
            "--min-lines", "5",
            "--min-tokens", "50",
            "--reporters", "json",
            "--output", str(work_dir),
            str(work_dir)
        ])

        # Read JSON output
        report_path = work_dir / "jscpd-report.json"
        if not report_path.exists():
            return (0, []) if detailed else 0

        with open(report_path) as f:
            data = json.load(f)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    duplicates = data.get("duplicates", [])
    count = len(duplicates)

    if not detailed:
        return count

    # Build detailed info
    details = []
    for dup in duplicates:
        first = dup.get("firstFile", {})
        second = dup.get("secondFile", {})
        details.append({
            "lines": dup.get("lines", 0),
            "tokens": dup.get("tokens", 0),
            "first_file": first.get("name"),
            "first_start": first.get("start"),
            "first_end": first.get("end"),
            "second_file": second.get("name"),
            "second_start": second.get("start"),
            "second_end": second.get("end"),
            "fragment": dup.get("fragment", "")[:200],  # Truncate long fragments
        })

    return count, details
