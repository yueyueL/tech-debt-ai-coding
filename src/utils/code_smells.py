"""
Code smell detection utilities.
"""

import hashlib
import re
from typing import List


def count_duplicates(lines: List[str], window: int = 5, detailed: bool = False):
    """
    Count duplicate code blocks using sliding window hash.
    
    Args:
        lines: Source code lines
        window: Number of lines to consider as a block
        detailed: If True, return (count, details) tuple with duplicate block info
        
    Returns:
        If detailed=False: int count of duplicates
        If detailed=True: (int count, list of duplicate block details)
    """
    if len(lines) < window:
        return (0, []) if detailed else 0
    
    hashes = {}
    hash_positions = {}  # Track positions for each hash
    
    for i in range(len(lines) - window + 1):
        chunk = "\n".join(lines[i : i + window]).strip()
        if not chunk:
            continue
        digest = hashlib.sha1(chunk.encode("utf-8")).hexdigest()
        hashes[digest] = hashes.get(digest, 0) + 1
        if digest not in hash_positions:
            hash_positions[digest] = []
        hash_positions[digest].append(i)
    
    # Build detailed info for duplicates, filtering overlapping windows
    duplicate_details = []
    total_count = 0
    
    for digest, positions in hash_positions.items():
        if len(positions) < 2:
            continue
        
        # Filter to non-overlapping positions only
        # Two blocks are truly duplicates if they're at least 'window' lines apart
        non_overlapping = [positions[0]]
        for pos in positions[1:]:
            if pos - non_overlapping[-1] >= window:
                non_overlapping.append(pos)
        
        if len(non_overlapping) >= 2:
            total_count += len(non_overlapping) - 1
            if detailed:
                first_pos = non_overlapping[0]
                block_content = "\n".join(lines[first_pos : first_pos + window])
                duplicate_details.append({
                    "block": block_content,
                    "occurrences": len(non_overlapping),
                    "line_numbers": [p + 1 for p in non_overlapping],  # 1-indexed
                })
    
    if not detailed:
        return total_count
    
    return total_count, duplicate_details


def count_nested_loops(lines: List[str]) -> int:
    """Count nested loop occurrences."""
    loop_pattern = re.compile(r"\b(for|while|foreach)\b")
    loop_indents: List[int] = []
    nested = 0
    for line in lines:
        if not loop_pattern.search(line):
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        while loop_indents and indent <= loop_indents[-1]:
            loop_indents.pop()
        if loop_indents:
            nested += 1
        loop_indents.append(indent)
    return nested


def count_long_functions(lines: List[str], threshold: int = 50) -> int:
    """Count functions longer than threshold lines."""
    func_pattern = re.compile(r"^\s*(def\s+\w+|function\s+\w+|\w+\s*=\s*\(.*\)\s*=>)")
    indices = [i for i, line in enumerate(lines) if func_pattern.match(line)]
    if not indices:
        return 0
    indices.append(len(lines))
    long_count = 0
    for start, end in zip(indices, indices[1:]):
        length = end - start
        if length > threshold:
            long_count += 1
    return long_count


def count_todos(lines: List[str]) -> int:
    """Count TODO comments."""
    todo_pattern = re.compile(r"\bTODO\b", re.IGNORECASE)
    return sum(1 for line in lines if todo_pattern.search(line))


def count_fixmes(lines: List[str]) -> int:
    """Count FIXME comments."""
    fixme_pattern = re.compile(r"\bFIXME\b", re.IGNORECASE)
    return sum(1 for line in lines if fixme_pattern.search(line))
