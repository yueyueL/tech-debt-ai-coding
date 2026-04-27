"""
Deep scan tool availability checks (CodeQL, SonarQube, Docker).
"""

import socket
import subprocess
from typing import Dict


def is_codeql_available() -> bool:
    """Check if CodeQL CLI is installed and available."""
    try:
        result = subprocess.run(
            ["codeql", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def is_sonarqube_available() -> bool:
    """Check if SonarQube server is running on localhost:9000."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 9000)) == 0
        sock.close()
        return result
    except Exception:
        return False


def is_docker_available() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_deep_scan_status() -> Dict[str, bool]:
    """Get availability status of all deep scan tools."""
    return {
        "codeql": is_codeql_available(),
        "sonarqube": is_sonarqube_available(),
        "docker": is_docker_available(),
    }


def print_deep_scan_status():
    """Print availability status of deep scan tools."""
    status = get_deep_scan_status()
    print("\n=== Deep Scan Tool Availability ===")
    print(f"  CodeQL:     {'✓ Available' if status['codeql'] else '✗ Not installed'}")
    print(f"  SonarQube:  {'✓ Running' if status['sonarqube'] else '✗ Not running on localhost:9000'}")
    print(f"  Docker:     {'✓ Available' if status['docker'] else '✗ Not installed'}")

    if not status['codeql']:
        print("\n  To install CodeQL:")
        print("    brew install codeql  # macOS")
        print("    # Or download from: https://github.com/github/codeql-cli-binaries")

    if not status['sonarqube']:
        print("\n  To start SonarQube:")
        print("    docker run -d --name sonarqube -p 9000:9000 sonarqube:latest")
        print("    # Then wait ~1 minute for startup and visit http://localhost:9000")
        print("    # Default login: admin/admin")

    print("")
