"""
Security vulnerability scanning using Semgrep.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional


def run_semgrep(code: str, filename: str) -> Dict:
    """Run Semgrep on code snippet and return security findings."""
    suffix = Path(filename).suffix or ".py"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        result = subprocess.run(
            ["semgrep", "scan", "--config=auto", "--json", str(temp_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout:
            data = json.loads(result.stdout)
            return parse_semgrep_results(data)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "vulnerabilities": [],
        "vulnerability_count": 0,
        "cwe_count": 0,
        "cwe_ids": [],
        "severity_counts": {"ERROR": 0, "WARNING": 0, "INFO": 0},
    }


def parse_semgrep_results(data: dict) -> Dict:
    """Parse Semgrep JSON output into structured metrics."""
    results = data.get("results", [])
    vulnerabilities: List[Dict] = []
    severity_counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    cwe_ids: set = set()

    for finding in results:
        severity = finding.get("extra", {}).get("severity", "INFO")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

        metadata = finding.get("extra", {}).get("metadata", {})
        cwes = metadata.get("cwe", [])
        if isinstance(cwes, str):
            cwes = [cwes]
        cwe_ids.update(cwes)

        vulnerabilities.append(
            {
                "rule_id": finding.get("check_id"),
                "severity": severity,
                "message": finding.get("extra", {}).get("message", ""),
                "line": finding.get("start", {}).get("line"),
                "cwe": cwes,
            }
        )

    return {
        "vulnerabilities": vulnerabilities,
        "vulnerability_count": len(vulnerabilities),
        "cwe_count": len(cwe_ids),
        "cwe_ids": list(cwe_ids),
        "severity_counts": severity_counts,
    }


def is_semgrep_available() -> bool:
    """Check if Semgrep CLI is installed."""
    try:
        result = subprocess.run(
            ["semgrep", "--version"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
