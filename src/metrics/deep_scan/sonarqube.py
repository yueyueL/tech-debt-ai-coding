"""
SonarQube integration for deep code quality and security analysis.
"""

import base64
import json
import logging
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from src.metrics.deep_scan.availability import is_sonarqube_available, is_docker_available

logger = logging.getLogger(__name__)


def run_sonarqube_analysis(
    repo_dir: Path,
    project_key: Optional[str] = None,
    timeout_seconds: int = 300,
) -> Optional[Dict[str, Any]]:
    """
    Run SonarQube analysis on a repository with detailed issue extraction.

    Requires:
        - SonarQube server running on localhost:9000
        - Docker (for sonar-scanner)
        - SONAR_TOKEN environment variable (optional but recommended)

    Args:
        repo_dir: Path to the repository
        project_key: SonarQube project key (auto-generated if not provided)
        timeout_seconds: Maximum time for analysis (increased default to 300s)

    Returns:
        Dict with SonarQube findings or None if analysis fails
    """
    if not is_sonarqube_available():
        logger.warning("SonarQube server not available on localhost:9000")
        return None

    if not is_docker_available():
        logger.warning("Docker not available for sonar-scanner")
        return None

    # Convert to absolute path (required for Docker volume mounts)
    repo_dir = Path(repo_dir).resolve()

    # Generate project key
    if not project_key:
        project_key = f"deep-scan-{os.getpid()}-{int(time.time())}"

    # Use SONAR_TOKEN if set, otherwise fall back to admin credentials
    sonar_token = os.environ.get("SONAR_TOKEN", "")
    sonar_user = os.environ.get("SONAR_USER", "admin")
    sonar_pass = os.environ.get("SONAR_PASSWORD", "admin")

    try:
        # Docker Desktop (macOS/Windows) requires host.docker.internal to reach host services.
        sonar_host_url = "http://localhost:9000"
        if platform.system() in {"Darwin", "Windows"}:
            sonar_host_url = "http://host.docker.internal:9000"

        # Run sonar-scanner via Docker
        scanner_cmd = [
            "docker", "run", "--rm",
            "--platform=linux/amd64",  # Required for ARM Macs
            "--network=host",
            "-v", f"{repo_dir}:/usr/src",
            "-w", "/usr/src",
            "sonarsource/sonar-scanner-cli",
            f"-Dsonar.host.url={sonar_host_url}",
            f"-Dsonar.projectKey={project_key}",
            "-Dsonar.sources=.",
            "-Dsonar.sourceEncoding=UTF-8",
            "-Dsonar.exclusions=**/node_modules/**,**/vendor/**,**/.git/**,**/test/**,**/tests/**,**/__pycache__/**",
        ]
        # Use token-based auth if available, otherwise user/password
        if sonar_token:
            scanner_cmd.append(f"-Dsonar.login={sonar_token}")
        else:
            scanner_cmd.append(f"-Dsonar.login={sonar_user}")
            scanner_cmd.append(f"-Dsonar.password={sonar_pass}")

        logger.info("Running SonarQube scanner...")
        result = subprocess.run(
            scanner_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode != 0:
            logger.warning(f"SonarQube scanner failed: {result.stderr[:500]}")
            return None

        # POLL FOR COMPLETION instead of fixed sleep
        report_task_path = repo_dir / ".scannerwork" / "report-task.txt"
        ce_task_id = None

        if report_task_path.exists():
            try:
                content = report_task_path.read_text()
                for line in content.splitlines():
                    if line.startswith("ceTaskId="):
                        ce_task_id = line.split("=")[1].strip()
                        break
            except Exception as e:
                logger.warning(f"Failed to read report-task.txt: {e}")

        if ce_task_id:
            logger.info(f"Polling SonarQube task {ce_task_id}...")
            if _poll_sonarqube_task(ce_task_id, sonar_user, sonar_pass, sonar_token):
                logger.info("SonarQube analysis successful")
            else:
                logger.warning("SonarQube task failed or timed out")
                return None
        else:
            # Fallback if task ID not found
            logger.warning("Could not find SonarQube task ID, waiting 10s fallback...")
            time.sleep(10)

        # Fetch results via API
        return _fetch_sonarqube_results(project_key, sonar_token)

    except subprocess.TimeoutExpired:
        logger.warning(f"SonarQube analysis timed out after {timeout_seconds}s")
        return None
    except Exception as e:
        logger.warning(f"SonarQube analysis error: {e}")
        return None
    finally:
        # Delete project from SonarQube to avoid clutter
        time.sleep(2)
        _delete_sonarqube_project(project_key, sonar_token)


def _poll_sonarqube_task(task_id: str, user: str, password: str, token: str, timeout: int = 60) -> bool:
    """Poll SonarQube Compute Engine task until success or failure."""
    base_url = "http://localhost:9000/api/ce/task"

    # Auth header
    if token:
        auth = base64.b64encode(f"{token}:".encode()).decode()
    else:
        auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(f"{base_url}?id={task_id}", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                task = data.get("task", {})
                status = task.get("status")

                if status == "SUCCESS":
                    return True
                elif status in ["FAILED", "CANCELED"]:
                    logger.error(f"SonarQube task failed: {task.get('errorMessage', 'Unknown error')}")
                    return False

                # IN_PROGRESS or PENDING
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Error polling SonarQube task: {e}")
            time.sleep(2)

    logger.warning("SonarQube task polling timed out")
    return False


def _fetch_sonarqube_results(project_key: str, token: str) -> Optional[Dict[str, Any]]:
    """Fetch detailed results from SonarQube API."""
    base_url = "http://localhost:9000/api"

    # Build auth header for API access
    sonar_user = os.environ.get("SONAR_USER", "admin")
    sonar_pass = os.environ.get("SONAR_PASSWORD", "admin")

    auth = base64.b64encode(f"{sonar_user}:{sonar_pass}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}

    try:
        # Fetch metrics
        metrics_url = f"{base_url}/measures/component?component={project_key}&metricKeys=bugs,vulnerabilities,code_smells,security_hotspots,cognitive_complexity,complexity,duplicated_lines_density,sqale_index,reliability_rating,security_rating"
        req = urllib.request.Request(metrics_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            metrics_data = json.loads(response.read().decode())

        # Fetch issues
        issues_url = f"{base_url}/issues/search?componentKeys={project_key}&ps=500"
        req = urllib.request.Request(issues_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            issues_data = json.loads(response.read().decode())

        # Parse metrics
        metrics = {}
        for measure in metrics_data.get("component", {}).get("measures", []):
            metric_name = measure.get("metric")
            value = measure.get("value")
            if metric_name in ["bugs", "vulnerabilities", "code_smells", "security_hotspots", "cognitive_complexity", "complexity", "sqale_index"]:
                metrics[metric_name] = int(float(value))
            elif metric_name == "duplicated_lines_density":
                metrics[metric_name] = float(value)
            else:
                metrics[metric_name] = value

        # Parse issues
        issues = []
        by_severity = {"BLOCKER": 0, "CRITICAL": 0, "MAJOR": 0, "MINOR": 0, "INFO": 0}
        by_type = {"BUG": 0, "VULNERABILITY": 0, "CODE_SMELL": 0, "SECURITY_HOTSPOT": 0}

        for issue in issues_data.get("issues", []):
            severity = issue.get("severity", "INFO")
            issue_type = issue.get("type", "CODE_SMELL")
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_type[issue_type] = by_type.get(issue_type, 0) + 1

            issues.append({
                "rule": issue.get("rule", ""),
                "severity": severity.lower(),
                "type": issue_type.lower().replace("_", " "),
                "message": issue.get("message", ""),
                "file": issue.get("component", "").split(":")[-1],
                "line": issue.get("line", 0),
                "effort": issue.get("effort", ""),
                "detected_by": "sonarqube",
                "tags": issue.get("tags", []),
            })

        return {
            "tool": "sonarqube",
            "metrics": metrics,
            "issues": issues,
            "issue_count": len(issues),
            "by_severity": by_severity,
            "by_type": by_type,
            "tech_debt_minutes": metrics.get("sqale_index", 0),
        }

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to fetch SonarQube results: {e}")
        return None


def _delete_sonarqube_project(project_key: str, token: str):
    """Delete a project from SonarQube to avoid clutter."""
    try:
        base_url = "http://localhost:9000/api"
        delete_url = f"{base_url}/projects/delete?project={project_key}"

        sonar_user = os.environ.get("SONAR_USER", "admin")
        sonar_pass = os.environ.get("SONAR_PASSWORD", "admin")
        if token:
            auth = base64.b64encode(f"{token}:".encode()).decode()
        else:
            auth = base64.b64encode(f"{sonar_user}:{sonar_pass}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}

        req = urllib.request.Request(delete_url, method="POST", headers=headers)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Ignore cleanup errors
