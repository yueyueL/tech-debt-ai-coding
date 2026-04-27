"""
Semgrep security scanning tool runner.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from src.utils.tools.common import run_tool, SEMGREP_CONFIGS


def run_semgrep_security(temp_path: Path, detailed: bool = False) -> Union[
    Dict[str, int],
    Tuple[Dict[str, int], List[Dict[str, Any]]]
]:
    """
    Run Semgrep for security scanning.

    Args:
        temp_path: Path to file to analyze
        detailed: If True, return list of findings

    Returns:
        If detailed=False: dict with vulnerability_count, severity counts
        If detailed=True: (summary dict, list of finding details)

    Note: Uses pinned rule configs (p/default, p/security-audit) instead of
    'auto' for reproducibility. The 'auto' config changes over time as
    Semgrep updates their registry, making research results non-reproducible.
    """
    # Build command with pinned configs
    cmd = ["semgrep", "--json", "--quiet"]
    for config in SEMGREP_CONFIGS:
        cmd.extend(["--config", config])
    cmd.append(str(temp_path))

    returncode, stdout, stderr = run_tool(cmd)

    summary = {
        "vulnerability_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
    }

    if returncode < 0 or not stdout.strip():
        return (summary, []) if detailed else summary

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return (summary, []) if detailed else summary

    results = data.get("results", [])
    findings = []

    for r in results:
        severity = r.get("extra", {}).get("severity", "INFO").upper()
        summary["vulnerability_count"] += 1
        if severity == "ERROR":
            summary["error_count"] += 1
        elif severity == "WARNING":
            summary["warning_count"] += 1
        else:
            summary["info_count"] += 1

        if detailed:
            findings.append({
                "rule": r.get("check_id"),
                "severity": severity,
                "message": r.get("extra", {}).get("message", ""),
                "line_start": r.get("start", {}).get("line"),
                "line_end": r.get("end", {}).get("line"),
                "path": r.get("path"),
            })

    if detailed:
        return summary, findings
    return summary
