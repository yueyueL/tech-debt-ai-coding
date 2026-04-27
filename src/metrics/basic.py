from pathlib import Path
from typing import Dict, List, Optional

from src.filters import classify_path, is_noise_path
from src.core.gitops import run_git


def _normalize_rename_path(path: str) -> str:
    if " => " not in path:
        return path
    if "{" in path and "}" in path:
        prefix, rest = path.split("{", 1)
        mid, suffix = rest.split("}", 1)
        if " => " in mid:
            _old, new = mid.split(" => ", 1)
            return f"{prefix}{new}{suffix}"
    return path.split(" => ", 1)[1]


def get_changed_files(repo_dir: Path, parent_sha: Optional[str], sha: str) -> List[dict]:
    if parent_sha:
        output = run_git(
            ["diff", "--name-status", parent_sha, sha],
            cwd=repo_dir,
        )
    else:
        output = run_git(
            ["diff-tree", "--root", "-r", "--name-status", sha],
            cwd=repo_dir,
        )

    changed = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            path = parts[2]
        elif len(parts) >= 2:
            path = parts[1]
        else:
            continue
        path = _normalize_rename_path(path)
        changed.append({"path": path, "status": status})
    return changed


def get_numstat(repo_dir: Path, parent_sha: Optional[str], sha: str) -> List[dict]:
    if parent_sha:
        output = run_git(["diff", "--numstat", parent_sha, sha], cwd=repo_dir)
    else:
        output = run_git(
            ["diff-tree", "--root", "-r", "--numstat", sha],
            cwd=repo_dir,
        )

    stats = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_raw, del_raw, path = parts[0], parts[1], parts[2]
        path = _normalize_rename_path(path)
        add = None if add_raw == "-" else int(add_raw)
        delete = None if del_raw == "-" else int(del_raw)
        stats.append({"path": path, "add": add, "del": delete})
    return stats


def summarize_patch(changed_files: List[dict], numstats: List[dict]) -> Dict[str, object]:
    stats_by_path = {item["path"]: item for item in numstats}
    total_files = len(changed_files)
    noise_count = 0
    code_count = 0
    doc_count = 0
    test_count = 0
    additions_total = 0
    deletions_total = 0
    additions_code = 0
    deletions_code = 0

    for entry in changed_files:
        path = entry.get("path") or ""
        if not path:
            continue
        is_noise = is_noise_path(path)
        if is_noise:
            noise_count += 1
        category = classify_path(path) if not is_noise else "other"
        if category == "code":
            code_count += 1
        elif category == "docs":
            doc_count += 1
        elif category == "test":
            test_count += 1

        stat = stats_by_path.get(path, {})
        add = stat.get("add")
        delete = stat.get("del")
        if isinstance(add, int):
            additions_total += add
            if category == "code":
                additions_code += add
        if isinstance(delete, int):
            deletions_total += delete
            if category == "code":
                deletions_code += delete

    noise_ratio = (noise_count / total_files) if total_files else 0.0
    touches_noise_only = total_files > 0 and noise_count == total_files

    return {
        "files_changed_total": total_files,
        "files_changed_code": code_count,
        "files_changed_docs": doc_count,
        "files_changed_tests": test_count,
        "additions_code": additions_code,
        "deletions_code": deletions_code,
        "additions_total": additions_total,
        "deletions_total": deletions_total,
        "touches_noise_only": touches_noise_only,
        "noise_file_ratio": noise_ratio,
    }
