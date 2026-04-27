import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.core.gitops import get_default_branch_head, run_git, get_commit_timestamp


logger = logging.getLogger(__name__)


def find_checkpoint_commit(repo_dir: Path, sha: str, target_days: int) -> Optional[str]:
    sha_ts = get_commit_timestamp(repo_dir, sha)
    if sha_ts is None:
        return None
    target_ts = sha_ts + int(target_days) * 86400
    try:
        _branch, head_sha = get_default_branch_head(repo_dir)
    except RuntimeError as exc:
        logger.warning("Unable to find default branch for checkpoint: %s", exc)
        return None

    try:
        output = run_git(
            ["log", "--reverse", "--format=%H%x1f%ct", f"{sha}..{head_sha}"],
            cwd=repo_dir,
        )
    except RuntimeError:
        return None

    for line in output.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 2:
            continue
        commit_sha, commit_ts = parts
        try:
            commit_ts_int = int(commit_ts)
        except ValueError:
            continue
        if commit_ts_int >= target_ts:
            return commit_sha
    return None


def _parse_blame(output: str) -> Tuple[int, Dict[str, int]]:
    total_lines = 0
    counts: Dict[str, int] = {}
    current_sha = None
    for line in output.splitlines():
        if line.startswith("\t"):
            total_lines += 1
            if current_sha:
                counts[current_sha] = counts.get(current_sha, 0) + 1
            continue
        parts = line.split()
        if parts and len(parts[0]) == 40:
            current_sha = parts[0]
    return total_lines, counts


def blame_line_attribution(
    repo_dir: Path,
    checkpoint_sha: str,
    file_path: str,
    target_sha: Optional[str] = None,
    blame_cache: Optional[dict] = None,
    repo_key: Optional[str] = None,
) -> Tuple[int, int]:
    cache_key = None
    if blame_cache is not None:
        cache_key = (repo_key or str(repo_dir), checkpoint_sha, file_path)
        if cache_key in blame_cache:
            total_lines, counts = blame_cache[cache_key]
        else:
            try:
                output = run_git(
                    ["blame", "--line-porcelain", checkpoint_sha, "--", file_path],
                    cwd=repo_dir,
                )
            except RuntimeError:
                return 0, 0
            total_lines, counts = _parse_blame(output)
            blame_cache[cache_key] = (total_lines, counts)
    else:
        try:
            output = run_git(
                ["blame", "--line-porcelain", checkpoint_sha, "--", file_path],
                cwd=repo_dir,
            )
        except RuntimeError:
            return 0, 0
        total_lines, counts = _parse_blame(output)

    lines_from_target = counts.get(target_sha, 0) if target_sha else 0
    return total_lines, lines_from_target


def compute_survival_for_commit(
    repo_dir: Path,
    sha: str,
    file_paths: List[str],
    checkpoints: List[int] = None,
    default_head: Optional[str] = None,
    blame_cache: Optional[dict] = None,
    repo_key: Optional[str] = None,
) -> Dict[str, Optional[float]]:
    if checkpoints is None:
        checkpoints = [7, 30, 60, 90]

    results: Dict[str, Optional[float]] = {}
    for days in checkpoints:
        checkpoint_sha = find_checkpoint_commit(repo_dir, sha, days)
        if checkpoint_sha is None:
            results[f"checkpoint_sha_{days}d"] = None
            results[f"survival_{days}d"] = None
            results[f"blamed_lines_total_{days}d"] = 0
            results[f"blamed_lines_from_target_{days}d"] = 0
            continue

        total_lines = 0
        lines_from_target = 0
        for path in file_paths:
            if not path:
                continue
            file_total, file_target = blame_line_attribution(
                repo_dir,
                checkpoint_sha,
                path,
                target_sha=sha,
                blame_cache=blame_cache,
                repo_key=repo_key,
            )
            total_lines += file_total
            lines_from_target += file_target

        survival_ratio = (lines_from_target / total_lines) if total_lines else 0.0
        results[f"checkpoint_sha_{days}d"] = checkpoint_sha
        results[f"survival_{days}d"] = survival_ratio
        results[f"blamed_lines_total_{days}d"] = total_lines
        results[f"blamed_lines_from_target_{days}d"] = lines_from_target

    return results


def compute_time_to_first_edit(
    repo_dir: Path,
    sha: str,
    file_path: str,
    default_head: Optional[str],
) -> Optional[float]:
    if not default_head:
        return None
    sha_ts = get_commit_timestamp(repo_dir, sha)
    if sha_ts is None:
        return None
    try:
        output = run_git(
            ["log", "--reverse", "--format=%ct", f"{sha}..{default_head}", "--", file_path],
            cwd=repo_dir,
        ).strip()
    except RuntimeError:
        return None
    if not output:
        return None
    first_line = output.splitlines()[0].strip()
    if not first_line:
        return None
    try:
        edit_ts = int(first_line)
    except ValueError:
        return None
    if edit_ts <= sha_ts:
        return None
    return (edit_ts - sha_ts) / 86400.0
