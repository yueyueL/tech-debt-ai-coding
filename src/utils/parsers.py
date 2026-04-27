"""
Diff and log parsing utilities.
"""

from typing import List, Tuple


def split_diff_by_file(content: str, fallback_path: str) -> List[Tuple[str, List[str]]]:
    """Split a diff into per-file patches."""
    patches = []
    current_path = None
    buffer: List[str] = []
    for line in content.splitlines():
        if line.startswith("diff --git"):
            if current_path and buffer:
                patches.append((current_path, buffer))
            buffer = []
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[3]
                if b_path.startswith("b/"):
                    b_path = b_path[2:]
                current_path = b_path
            else:
                current_path = None
            continue
        if line.startswith("+++ "):
            path = line.split(" ", 1)[1].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path != "/dev/null":
                current_path = path
            continue
        if current_path is None:
            continue
        buffer.append(line)
    if current_path and buffer:
        patches.append((current_path, buffer))
    if not patches and fallback_path:
        patches.append((fallback_path, content.splitlines()))
    return patches


def extract_added_lines(lines: List[str]) -> List[str]:
    """Extract only added lines from diff."""
    added = []
    for line in lines:
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
    return added


def parse_log_entries(output: str) -> List[Tuple[str, str, str, int, str]]:
    """Parse git log output into structured entries.
    
    Expected format: %H|%an|%ae|%at|%s
    Returns: list of (commit_hash, author_name, author_email, timestamp, subject)
    """
    entries = []
    for line in output.splitlines():
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        commit_hash, author_name, author_email, ts, subject = parts
        try:
            ts_int = int(ts)
        except ValueError:
            ts_int = 0
        entries.append((commit_hash, author_name, author_email, ts_int, subject))
    return entries
