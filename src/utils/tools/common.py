"""
Common tool runner infrastructure and version/environment queries.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# Rule overrides for severity adjustments (to reduce noise)
RULE_SEVERITY_OVERRIDES = {
    # Downgrade Math.random() warning to LOW (Info) as it's often used for IDs/UI
    "node_insecure_random_generator": "LOW",
    "insecure_random": "LOW",
    # Downgrade subprocess import to LOW
    "B404": "LOW",
}

# Pylint findings that are highly environment-dependent at scale.
#
# Our analysis runs on raw repository snapshots without installing project deps
# (required for 100k+ repo scale). Pylint will otherwise emit a large number of
# false positives for missing imports, which are not attributable to the commit.
#
# We suppress these to keep metrics defensible and reduce noise.
PYLINT_DISABLED_SYMBOLS = {
    "import-error",         # E0401: cannot import module (deps not installed / temp context)
    "no-name-in-module",    # E0611: name not found in module (often dependency stub mismatch)
}

# Pinned Semgrep rule configurations for reproducibility
# Using specific rule packs instead of 'auto' which changes over time
SEMGREP_CONFIGS = [
    "p/default",      # Core default rules (stable)
    "p/security-audit",  # Security-focused rules
]


# Default timeout for external tool execution (seconds).
# Prevents hangs when tools encounter malformed input at scale.
# 5 minutes is generous but prevents indefinite hangs.
TOOL_TIMEOUT_SECONDS = 300


def run_tool(command: list[str], cwd: Optional[Path] = None, timeout: Optional[int] = None, env: Optional[dict] = None) -> Tuple[int, str, str]:
    """
    Run external tool and return exit code, stdout, stderr.

    Args:
        command: Command + arguments
        cwd: Working directory
        timeout: Override timeout in seconds (default: TOOL_TIMEOUT_SECONDS)
        env: Environment variables (default: inherit from os.environ)
    """
    effective_timeout = timeout if timeout is not None else TOOL_TIMEOUT_SECONDS
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            cwd=str(cwd) if cwd else None,
            timeout=effective_timeout,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        import logging
        logging.getLogger(__name__).warning(
            "Tool timed out after %ds: %s", effective_timeout, " ".join(command[:3])
        )
        return -2, "", f"Tool timed out after {effective_timeout}s: {command[0]}"
    except FileNotFoundError:
        # Tool not found in PATH. When running inside a venv without "activate",
        # the venv's bin directory may not be on PATH even though the executables
        # exist. Fall back to:
        # - Path(sys.executable).parent/<tool> (don't resolve symlinks)
        # - <sys.prefix>/bin/<tool> (POSIX venv)
        # - <sys.prefix>/Scripts/<tool>(.exe) (Windows venv)
        try:
            import sys
            import platform
            tool_name = command[0]
            candidates: list[Path] = []

            # 1) Sibling of the current interpreter (venv bin/Scripts)
            candidates.append(Path(sys.executable).parent / tool_name)

            # 2) sys.prefix-based venv paths
            prefix = Path(sys.prefix)
            if platform.system() == "Windows":
                candidates.append(prefix / "Scripts" / tool_name)
                candidates.append(prefix / "Scripts" / f"{tool_name}.exe")
            else:
                candidates.append(prefix / "bin" / tool_name)

            for candidate in candidates:
                if not candidate.exists():
                    continue
                resolved_cmd = [str(candidate), *command[1:]]
                result = subprocess.run(
                    resolved_cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(cwd) if cwd else None,
                    timeout=effective_timeout,
                )
                return result.returncode, result.stdout, result.stderr
        except Exception:
            pass
        return -1, "", f"Tool not found: {command[0]}"


def get_tool_versions() -> Dict[str, str]:
    """
    Get versions of all analysis tools for reproducibility.

    Returns:
        Dict mapping tool name to version string
    """
    versions = {}

    # Semgrep
    ret, stdout, _ = run_tool(["semgrep", "--version"])
    if ret == 0 and stdout.strip():
        versions["semgrep"] = stdout.strip().split("\n")[0]

    # Pylint
    ret, stdout, _ = run_tool(["pylint", "--version"])
    if ret == 0 and stdout.strip():
        # First line is like "pylint 3.0.2"
        versions["pylint"] = stdout.strip().split("\n")[0]

    # ESLint
    ret, stdout, _ = run_tool(["eslint", "--version"])
    if ret == 0 and stdout.strip():
        versions["eslint"] = stdout.strip()

    # Bandit
    ret, stdout, _ = run_tool(["bandit", "--version"])
    if ret == 0 and stdout.strip():
        versions["bandit"] = stdout.strip().split("\n")[0]

    # Radon
    ret, stdout, _ = run_tool(["radon", "--version"])
    if ret == 0 and stdout.strip():
        versions["radon"] = stdout.strip()

    # CodeQL (if available)
    ret, stdout, _ = run_tool(["codeql", "version"])
    if ret == 0 and stdout.strip():
        versions["codeql"] = stdout.strip().split("\n")[0]

    # njsscan (if available)
    ret, stdout, _ = run_tool(["njsscan", "--version"])
    if ret == 0 and stdout.strip():
        versions["njsscan"] = stdout.strip().split("\n")[0]

    # Git version
    ret, stdout, _ = run_tool(["git", "--version"])
    if ret == 0 and stdout.strip():
        versions["git"] = stdout.strip()

    # Record pinned Semgrep configs
    versions["semgrep_configs"] = ",".join(SEMGREP_CONFIGS)

    return versions


def get_environment_info() -> Dict[str, Any]:
    """
    Get comprehensive environment information for reproducibility.

    Returns:
        Dict with Python version, OS info, and other environment details.
    """
    import platform
    import sys
    import os
    from datetime import datetime, timezone

    env_info = {
        # Python environment
        "python_version": sys.version,
        "python_executable": sys.executable,
        "python_platform": platform.python_implementation(),

        # Operating system
        "os_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "os_machine": platform.machine(),
        "os_platform": platform.platform(),

        # Timestamp
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "timezone": "UTC",

        # Working directory
        "working_directory": os.getcwd(),

        # Environment variables that might affect analysis
        "env_path_set": "PATH" in os.environ,
        "env_home": os.environ.get("HOME", "not_set"),
    }

    # Try to get analyzer tool git hash for exact reproducibility
    try:
        analyzer_root = Path(__file__).resolve().parents[3]
        if (analyzer_root / ".git").exists():
            ret, stdout, _ = run_tool(
                ["git", "rev-parse", "HEAD"],
                cwd=analyzer_root
            )
            if ret == 0 and stdout.strip():
                env_info["analyzer_git_sha"] = stdout.strip()

            # Check if working tree is clean
            ret, stdout, _ = run_tool(
                ["git", "status", "--porcelain"],
                cwd=analyzer_root
            )
            env_info["analyzer_git_clean"] = (ret == 0 and not stdout.strip())
    except Exception:
        pass

    return env_info
