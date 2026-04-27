"""
CodeQL integration for deep security and quality analysis.
"""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from src.metrics.deep_scan.availability import is_codeql_available

logger = logging.getLogger(__name__)


CODEQL_LANGUAGE_MAP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "javascript",  # CodeQL uses JS extractor for TS
    "java": "java",
    "go": "go",
    "ruby": "ruby",
    "csharp": "csharp",
    "cpp": "cpp",
    "c": "cpp",
}

CODEQL_QUERY_SUITES = {
    # Format: codeql/{language}-queries:codeql-suites/{language}-security-and-quality.qls
    "python": "codeql/python-queries:codeql-suites/python-security-and-quality.qls",
    "javascript": "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls",
    "java": "codeql/java-queries:codeql-suites/java-security-and-quality.qls",
    "go": "codeql/go-queries:codeql-suites/go-security-and-quality.qls",
    "ruby": "codeql/ruby-queries:codeql-suites/ruby-security-and-quality.qls",
    "csharp": "codeql/csharp-queries:codeql-suites/csharp-security-and-quality.qls",
    "cpp": "codeql/cpp-queries:codeql-suites/cpp-security-and-quality.qls",
}


def run_codeql_analysis(
    repo_dir: Path,
    language: str,
    timeout_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Run CodeQL analysis on a repository.

    Args:
        repo_dir: Path to the repository
        language: Programming language (python, javascript, java, go, etc.)
        timeout_seconds: Maximum time for analysis

    Returns:
        Dict with CodeQL findings or None if analysis fails:
        {
            "issues": [...],
            "issue_count": int,
            "by_severity": {"error": int, "warning": int, "note": int},
            "by_cwe": {"CWE-79": int, ...},
            "rules_triggered": [...],
        }
    """
    if not is_codeql_available():
        logger.warning("CodeQL CLI not available")
        return None

    # Convert to absolute path
    repo_dir = Path(repo_dir).resolve()

    codeql_lang = CODEQL_LANGUAGE_MAP.get(language)
    if not codeql_lang:
        logger.warning(f"CodeQL does not support language: {language}")
        return None

    # Create temp directory for CodeQL database
    work_dir = Path(tempfile.mkdtemp(prefix="codeql_"))
    db_path = work_dir / "codeql-db"
    sarif_path = work_dir / "results.sarif"

    try:
        # Step 1: Create CodeQL database
        logger.info(f"Creating CodeQL database for {language}...")
        create_cmd = [
            "codeql", "database", "create",
            str(db_path),
            f"--language={codeql_lang}",
            f"--source-root={repo_dir}",
            "--overwrite",
        ]

        result = subprocess.run(
            create_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            logger.warning(f"CodeQL database creation failed: {result.stderr[:500]}")
            return None

        # Step 2: Run queries
        logger.info("Running CodeQL queries...")
        query_suite = CODEQL_QUERY_SUITES.get(codeql_lang, f"{codeql_lang}-security-and-quality.qls")

        analyze_cmd = [
            "codeql", "database", "analyze",
            str(db_path),
            query_suite,
            "--format=sarif-latest",
            f"--output={sarif_path}",
            "--threads=0",  # Use all available threads
        ]

        result = subprocess.run(
            analyze_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            logger.warning(f"CodeQL analysis failed: {result.stderr[:500]}")
            return None

        # Step 3: Parse SARIF results
        if not sarif_path.exists():
            logger.warning("CodeQL did not produce SARIF output")
            return None

        with open(sarif_path, 'r') as f:
            sarif_data = json.load(f)

        return _parse_codeql_sarif(sarif_data)

    except subprocess.TimeoutExpired:
        logger.warning(f"CodeQL analysis timed out after {timeout_seconds}s")
        return None
    except Exception as e:
        logger.warning(f"CodeQL analysis error: {e}")
        return None
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _parse_codeql_sarif(sarif_data: Dict) -> Dict[str, Any]:
    """Parse CodeQL SARIF output into structured findings."""
    issues = []
    by_severity = {"error": 0, "warning": 0, "note": 0}
    by_cwe: Dict[str, int] = {}
    rules_triggered = set()

    for run in sarif_data.get("runs", []):
        # Get rule definitions
        rules = {r["id"]: r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}

        for result in run.get("results", []):
            rule_id = result.get("ruleId", "unknown")
            rules_triggered.add(rule_id)

            # Get rule metadata
            rule = rules.get(rule_id, {})
            severity = result.get("level", "warning")
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # Extract CWE
            cwe_tags = [t for t in rule.get("properties", {}).get("tags", []) if t.startswith("cwe")]
            for cwe in cwe_tags:
                by_cwe[cwe.upper()] = by_cwe.get(cwe.upper(), 0) + 1

            # Get location
            locations = result.get("locations", [])
            location = locations[0] if locations else {}
            physical = location.get("physicalLocation", {})
            artifact = physical.get("artifactLocation", {})
            region = physical.get("region", {})

            issue = {
                "rule": rule_id,
                "severity": severity,
                "message": result.get("message", {}).get("text", ""),
                "file": artifact.get("uri", ""),
                "line": region.get("startLine", 0),
                "column": region.get("startColumn", 0),
                "cwe": cwe_tags,
                "type": "security" if "security" in rule.get("properties", {}).get("tags", []) else "quality",
                "detected_by": "codeql",
            }
            issues.append(issue)

    return {
        "tool": "codeql",
        "issues": issues,
        "issue_count": len(issues),
        "by_severity": by_severity,
        "by_cwe": by_cwe,
        "rules_triggered": list(rules_triggered),
    }
