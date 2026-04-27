"""
Deep Scan Module: High-accuracy analysis using CodeQL and SonarQube.

Re-exports all public symbols so existing imports like
``from src.metrics.deep_scan import run_deep_scan`` continue to work.
"""

# --- availability ---
from src.metrics.deep_scan.availability import (
    is_codeql_available,
    is_sonarqube_available,
    is_docker_available,
    get_deep_scan_status,
    print_deep_scan_status,
)

# --- codeql ---
from src.metrics.deep_scan.codeql import (
    run_codeql_analysis,
    CODEQL_LANGUAGE_MAP,
    CODEQL_QUERY_SUITES,
)

# --- sonarqube ---
from src.metrics.deep_scan.sonarqube import run_sonarqube_analysis

# --- unified orchestration ---
from src.metrics.deep_scan.unified import (
    run_deep_scan,
    analyze_commit_deep,
    analyze_ai_commits_deep,
)

__all__ = [
    # availability
    "is_codeql_available",
    "is_sonarqube_available",
    "is_docker_available",
    "get_deep_scan_status",
    "print_deep_scan_status",
    # codeql
    "run_codeql_analysis",
    "CODEQL_LANGUAGE_MAP",
    "CODEQL_QUERY_SUITES",
    # sonarqube
    "run_sonarqube_analysis",
    # unified
    "run_deep_scan",
    "analyze_commit_deep",
    "analyze_ai_commits_deep",
]
