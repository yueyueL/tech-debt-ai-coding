"""Metrics computation modules."""

from src.metrics.basic import get_changed_files, get_numstat, summarize_patch
from src.metrics.complexity import (
    compute_cognitive_complexity,
    compute_file_complexity_from_blob,
    compute_commit_complexity_delta,
)
from src.metrics.security import run_semgrep, is_semgrep_available
from src.metrics.survival import (
    find_checkpoint_commit,
    blame_line_attribution,
    compute_survival_for_commit,
    compute_time_to_first_edit,
)
from src.metrics.deep_scan import (
    run_deep_scan,
    run_codeql_analysis,
    run_sonarqube_analysis,
    is_codeql_available,
    is_sonarqube_available,
    get_deep_scan_status,
)

__all__ = [
    "get_changed_files",
    "get_numstat",
    "summarize_patch",
    "compute_cognitive_complexity",
    "compute_file_complexity_from_blob",
    "compute_commit_complexity_delta",
    "run_semgrep",
    "is_semgrep_available",
    "find_checkpoint_commit",
    "blame_line_attribution",
    "compute_survival_for_commit",
    "compute_time_to_first_edit",
    # Deep scan (Tier-2)
    "run_deep_scan",
    "run_codeql_analysis",
    "run_sonarqube_analysis",
    "is_codeql_available",
    "is_sonarqube_available",
    "get_deep_scan_status",
]
