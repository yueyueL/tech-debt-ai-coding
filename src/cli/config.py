"""
CLI configuration: prompts, load/save settings, pipeline invocation.
"""

import json
from pathlib import Path

from src.core.config import OUT_DIR, REPO_CACHE_DIR, DEFAULT_PIPELINE_SETTINGS
from scripts.run_pipeline import main as run_pipeline_main


def _prompt(label: str, default: str | None = None) -> str:
    if default:
        prompt = f"{label} [{default}]: "
    else:
        prompt = f"{label}: "
    value = input(prompt).strip()
    return value or (default or "")


def _yes_no(label: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{label} ({hint}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def _load_config() -> dict:
    defaults = {
        "out_dir": str(OUT_DIR),
        "repo_cache": str(REPO_CACHE_DIR),
        "checkpoint": str(OUT_DIR / "pipeline_checkpoint.json"),
        "no_shallow": False,
        "log_level": "INFO",
        "last_input": "",
        "sonarqube_only": False,
        # Save per-commit detailed outputs under out/<repo>/debug/*.json
        "save_details": True,
        "workers": 4,  # File-level workers per repo
        "parallel": 4,  # Repo-level workers for batch analysis
        "limit": 0,  # Limit number of commits to analyze (0 = all)
        # Deep scan options (Tier-2: CodeQL/SonarQube)
        "deep_scan": False,  # Enable deep scan for repos with issues
        "deep_scan_tools": "codeql,sonarqube",  # Tools to use
    }
    if not DEFAULT_PIPELINE_SETTINGS.exists():
        return defaults
    try:
        data = json.loads(DEFAULT_PIPELINE_SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defaults
    if not isinstance(data, dict):
        return defaults
    defaults.update({k: v for k, v in data.items() if k in defaults})
    return defaults


def _save_config(config: dict) -> None:
    DEFAULT_PIPELINE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_PIPELINE_SETTINGS.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _run_pipeline(input_path: str, config: dict) -> int:
    argv = [
        "--input",
        input_path,
        "--out-dir",
        config["out_dir"],
        "--repo-cache",
        config["repo_cache"],
        "--checkpoint",
        config["checkpoint"],
        "--log-level",
        config["log_level"],
    ]
    if config.get("no_shallow"):
        argv.append("--no-shallow")
    # Save detailed per-commit outputs by default; allow opting out.
    save_details = config.get("save_details", config.get("debug", True))
    if not save_details:
        argv.append("--not-save-details")
    # Pass SonarQube-only mode if enabled
    if config.get("sonarqube_only"):
        argv.append("--sonarqube-only")
    # Pass workers count
    workers = config.get("workers", 4)
    argv.extend(["--workers", str(workers)])
    # Pass limit if set
    limit = config.get("limit", 0)
    if limit > 0:
        argv.extend(["--limit", str(limit)])

    # Deep scan options
    if config.get("deep_scan"):
        argv.append("--deep-scan")
        tools = config.get("deep_scan_tools", "codeql,sonarqube")
        argv.extend(["--deep-scan-tools", tools])

    return run_pipeline_main(argv)
