import re
from pathlib import Path
from typing import Dict, List, Optional

import lizard

from src.core.gitops import run_git


# Patterns for cognitive complexity calculation
CONTROL_FLOW_KEYWORDS = re.compile(
    r"\b(if|else|elif|for|while|switch|case|catch|except|with|"
    r"try|finally|\?\s*:|\&\&|\|\|)\b"
)
NESTING_KEYWORDS = re.compile(r"\b(if|for|while|switch|try|with|def|function|class)\b")
BREAK_KEYWORDS = re.compile(r"\b(break|continue|goto)\b")
RECURSION_PATTERN = re.compile(r"\b(\w+)\s*\(")


def compute_cognitive_complexity(text: str) -> int:
    """
    Compute cognitive complexity based on SonarQube's algorithm.
    
    Increments for:
    - Control flow structures (if, for, while, etc.)
    - Nesting (each level adds +1 to increment)
    - Breaks in linear flow (break, continue)
    - Boolean operators in conditions
    """
    if not text:
        return 0

    complexity = 0
    nesting_level = 0
    indent_stack: List[int] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue

        # Calculate current indentation
        indent = len(line) - len(line.lstrip())

        # Adjust nesting level based on indentation
        while indent_stack and indent <= indent_stack[-1]:
            indent_stack.pop()
            nesting_level = max(0, nesting_level - 1)

        # Control flow adds base complexity + nesting penalty
        for match in CONTROL_FLOW_KEYWORDS.finditer(stripped):
            keyword = match.group(1)
            if keyword in ("&&", "||", "?"):
                complexity += 1  # Boolean operators add flat +1
            elif keyword == "else":
                complexity += 1  # else adds flat +1
            else:
                complexity += 1 + nesting_level  # Base + nesting

        # Break/continue adds flat +1
        if BREAK_KEYWORDS.search(stripped):
            complexity += 1

        # Track nesting
        if NESTING_KEYWORDS.search(stripped):
            indent_stack.append(indent)
            nesting_level += 1

    return complexity


def compute_file_complexity_from_blob(text: str, filename: str) -> Dict[str, int]:
    if not text:
        return {"cyclomatic_complexity": 0, "cognitive_complexity": 0, "n_functions": 0}
    analysis = lizard.analyze_file.analyze_source_code(filename, text)
    total_cc = 0
    for function in analysis.function_list:
        total_cc += function.cyclomatic_complexity
    
    # Compute cognitive complexity using our custom implementation
    cognitive_cc = compute_cognitive_complexity(text)
    
    return {
        "cyclomatic_complexity": total_cc,
        "cognitive_complexity": cognitive_cc,
        "n_functions": len(analysis.function_list),
    }


def _get_blob(repo_dir: Path, sha: str, path: str) -> Optional[str]:
    try:
        return run_git(["show", f"{sha}:{path}"], cwd=repo_dir)
    except RuntimeError:
        return None


def compute_commit_complexity_delta(
    repo_dir: Path,
    parent_sha: Optional[str],
    sha: str,
    file_paths: List[str],
) -> Dict[str, float]:
    total_cc_parent = 0
    total_cc_sha = 0
    functions_parent = 0
    functions_sha = 0

    for path in file_paths:
        if parent_sha:
            parent_blob = _get_blob(repo_dir, parent_sha, path)
        else:
            parent_blob = None
        sha_blob = _get_blob(repo_dir, sha, path)

        if parent_blob is not None:
            parent_metrics = compute_file_complexity_from_blob(parent_blob, path)
            total_cc_parent += parent_metrics["cyclomatic_complexity"]
            functions_parent += parent_metrics["n_functions"]

        if sha_blob is not None:
            sha_metrics = compute_file_complexity_from_blob(sha_blob, path)
            total_cc_sha += sha_metrics["cyclomatic_complexity"]
            functions_sha += sha_metrics["n_functions"]

    avg_cc_parent = (total_cc_parent / functions_parent) if functions_parent else 0.0
    avg_cc_sha = (total_cc_sha / functions_sha) if functions_sha else 0.0
    delta_total_cc = total_cc_sha - total_cc_parent

    return {
        "total_cc_parent": float(total_cc_parent),
        "total_cc_sha": float(total_cc_sha),
        "delta_total_cc": float(delta_total_cc),
        "avg_cc_parent": float(avg_cc_parent),
        "avg_cc_sha": float(avg_cc_sha),
    }
