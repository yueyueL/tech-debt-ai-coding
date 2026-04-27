"""
SonarQube analysis tool runner.
"""

import json
import os
import platform
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.tools.common import run_tool


def run_sonarqube(temp_path: Path, detailed: bool = False) -> Optional[Dict[str, Any]]:
    """
    Run SonarQube analysis using Docker for exact CursorStudy metric parity.

    This function attempts to use SonarQube via Docker for accurate metrics.
    Falls back to None if Docker/SonarQube is not available.

    Returns:
        Dict with SonarQube metrics or None if not available:
        {
            "cognitive_complexity": int,
            "cyclomatic_complexity": int,
            "duplicated_lines_density": float,
            "bugs": int,
            "vulnerabilities": int,
            "code_smells": int,
            "sqale_index": int,  # Technical debt in minutes
        }
    """
    import shutil
    import tempfile

    # Check if Docker is available
    returncode, _, _ = run_tool(["docker", "--version"])
    if returncode != 0:
        return None

    # Create work directory in /tmp for Docker accessibility on macOS
    # The default tempfile.mkdtemp() uses /var/folders which Docker can't mount
    work_dir = Path(tempfile.mkdtemp(dir="/tmp"))
    try:
        # Copy file to work directory
        target_file = work_dir / temp_path.name
        shutil.copy(temp_path, target_file)

        # Create sonar-project.properties
        props_file = work_dir / "sonar-project.properties"
        # Unique project key for parallel processing (PID + ThreadID)
        project_key = f"temp-analysis-{os.getpid()}-{threading.get_ident()}"
        props_content = f"""sonar.projectKey={project_key}
sonar.projectName=Temp Analysis
sonar.sources=.
sonar.sourceEncoding=UTF-8
"""
        props_file.write_text(props_content)

        # Try to use local SonarQube if available (port 9000)
        # First check if SonarQube is running
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sonar_available = sock.connect_ex(('localhost', 9000)) == 0
        sock.close()

        if not sonar_available:
            # SonarQube server not running - return None
            # User would need to start: docker run -d --name sonarqube -p 9000:9000 sonarqube:latest
            return None

        # Run sonar-scanner using Docker
        # -w /usr/src sets the working directory inside container so it finds sonar-project.properties
        # Use sonar.login for authentication (compatible with all SonarQube versions)
        sonar_token = os.environ.get("SONAR_TOKEN", "")
        sonar_user = os.environ.get("SONAR_USER", "admin")
        sonar_pass = os.environ.get("SONAR_PASSWORD", "admin")

        # Docker Desktop (macOS/Windows) requires host.docker.internal to reach host services.
        sonar_host_url = "http://localhost:9000"
        if platform.system() in {"Darwin", "Windows"}:
            sonar_host_url = "http://host.docker.internal:9000"

        scanner_args = [
            "docker", "run", "--rm",
            "--network=host",
            "-v", f"{work_dir}:/usr/src",
            "-w", "/usr/src",
            "sonarsource/sonar-scanner-cli",
            f"-Dsonar.host.url={sonar_host_url}",
        ]
        # Use token-based auth if available, otherwise user/password
        if sonar_token:
            scanner_args.append(f"-Dsonar.login={sonar_token}")
        else:
            scanner_args.append(f"-Dsonar.login={sonar_user}")
            scanner_args.append(f"-Dsonar.password={sonar_pass}")

        returncode, stdout, stderr = run_tool(scanner_args, cwd=work_dir)

        if returncode != 0:
            return None

        # Query SonarQube API for metrics
        import urllib.request
        import urllib.error
        import time
        import base64

        def _basic_auth(user: str, password: str) -> str:
            return base64.b64encode(f"{user}:{password}".encode()).decode()

        # Prefer user/password for API access (analysis tokens often can't read APIs).
        # Fall back to token if user/password fails and token is set.
        auth_candidates: list[str] = []
        if sonar_user and sonar_pass:
            auth_candidates.append(_basic_auth(sonar_user, sonar_pass))
        if sonar_token:
            auth_candidates.append(_basic_auth(sonar_token, ""))

        # Wait for SonarQube to process analysis (prefer polling CE task).
        report_task_path = work_dir / ".scannerwork" / "report-task.txt"
        ce_task_id = None
        if report_task_path.exists():
            try:
                content = report_task_path.read_text(encoding="utf-8", errors="replace")
                for line in content.splitlines():
                    if line.startswith("ceTaskId="):
                        ce_task_id = line.split("=", 1)[1].strip()
                        break
            except Exception:
                ce_task_id = None

        if ce_task_id and auth_candidates:
            ce_url = f"http://localhost:9000/api/ce/task?id={ce_task_id}"
            start = time.time()
            while time.time() - start < 60:
                try:
                    req = urllib.request.Request(ce_url, headers={"Authorization": f"Basic {auth_candidates[0]}"})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        payload = json.loads(response.read().decode())
                    status = (payload.get("task", {}) or {}).get("status")
                    if status == "SUCCESS":
                        break
                    if status in {"FAILED", "CANCELED"}:
                        return None
                except Exception:
                    # fall back to retrying for up to 60s
                    pass
                time.sleep(2)
        else:
            # Fallback: fixed wait
            time.sleep(8)

        metrics_url = (
            "http://localhost:9000/api/measures/component"
            f"?component={project_key}"
            "&metricKeys=cognitive_complexity,complexity,duplicated_lines_density,bugs,vulnerabilities,code_smells,sqale_index"
        )

        data = None
        used_auth = None
        for auth in auth_candidates:
            try:
                req = urllib.request.Request(metrics_url, headers={"Authorization": f"Basic {auth}"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read().decode())
                used_auth = auth
                break
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
                continue

        if not data:
            return None

        # Parse metrics
        result = {}
        for measure in data.get("component", {}).get("measures", []):
            metric = measure.get("metric")
            value = measure.get("value")
            if metric == "cognitive_complexity":
                result["cognitive_complexity"] = int(value)
            elif metric == "complexity":
                result["cyclomatic_complexity"] = int(value)
            elif metric == "duplicated_lines_density":
                result["duplicated_lines_density"] = float(value)
            elif metric == "bugs":
                result["bugs"] = int(value)
            elif metric == "vulnerabilities":
                result["vulnerabilities"] = int(value)
            elif metric == "code_smells":
                result["code_smells"] = int(value)
            elif metric == "sqale_index":
                result["sqale_index"] = int(value)  # Tech debt in minutes

        # Cleanup: delete temp project to avoid cluttering SonarQube
        if used_auth:
            try:
                delete_url = f"http://localhost:9000/api/projects/delete?project={project_key}"
                req = urllib.request.Request(
                    delete_url,
                    method="POST",
                    headers={"Authorization": f"Basic {used_auth}"},
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass

        return result if result else None

    except Exception as e:
        return None
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
