#!/usr/bin/env python3
"""
Pipeline runner for AI commit analysis.

This script orchestrates the full analysis pipeline:
1. Load commits from input JSON file
2. Clone/update repository
3. Run debt analysis on each commit
4. Calculate survival metrics
5. Save results

Usage:
    python scripts/run_pipeline.py --input data/claude/PostHog_posthog_commits.json
    python scripts/run_pipeline.py --input data/claude/ --batch
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.config import OUT_DIR, REPO_CACHE_DIR
from src.core.loaders import load_commits, save_results
from src.core.gitops import clone_or_update_repo, ensure_commit, get_default_branch_head, is_ancestor
from src.analyzers.debt import analyze_commit_debt
from src.analyzers.lifecycle import analyze_commit_lifecycle
from src.analyzers.destiny import analyze_code_destiny
from src.metrics.issue_survival import analyze_issue_survival

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def analyze_repo_commits(
    input_file: Path,
    out_dir: Path,
    repo_cache: Path,
    checkpoint_file: Optional[Path] = None,
    no_shallow: bool = False,
    save_details: bool = True,
    sonarqube_only: bool = False,
    workers: int = 4,
    limit: int = 0,
    include_all_commits: bool = True,
    deep_scan: bool = False,
) -> Dict[str, Any]:
    """
    Run full analysis pipeline on commits from a single repo file.
    
    Args:
        input_file: Path to JSON file with AI commits
        out_dir: Output directory for results
        repo_cache: Directory to cache cloned repos
        checkpoint_file: Optional checkpoint file for resuming
        no_shallow: If True, clone full repo (not shallow)
        save_details: If True, save per-commit detail files (default)
        sonarqube_only: If True, use only SonarQube for analysis
        workers: Number of parallel workers
        limit: Max commits to analyze (0 = all)
        include_all_commits: If True, analyze all commits (default). If False, only analyze commits on main branch.
        deep_scan: If True, run extended analysis (e.g., lifecycle)
        
    Returns:
        Summary dict with analysis results
    """
    # Load commits
    logger.info("Loading commits from %s", input_file)
    commits = list(load_commits(input_file))
    
    if not commits:
        logger.warning("No commits found in %s", input_file)
        return {"status": "error", "message": "No commits found"}
    
    # Apply limit
    if limit > 0 and len(commits) > limit:
        logger.info("Limiting to first %d commits (of %d)", limit, len(commits))
        commits = commits[:limit]
    
    logger.info("Loaded %d commits", len(commits))
    
    # Get repo info from first commit
    first_commit = commits[0]
    repo_name = first_commit.get("full_name") or first_commit.get("repo", "")
    repo_url = first_commit.get("repo_url", "")
    
    if not repo_name and repo_url:
        # Extract repo name from URL
        if "github.com" in repo_url:
            parts = repo_url.rstrip("/").split("/")
            if len(parts) >= 2:
                repo_name = f"{parts[-2]}/{parts[-1]}"
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
    
    if not repo_name:
        logger.error("Could not determine repo name from commits")
        return {"status": "error", "message": "Could not determine repo name"}
    
    logger.info("Repository: %s", repo_name)
    
    # Setup output directory for this repo
    repo_folder = repo_name.replace("/", "_")
    repo_out_dir = out_dir / repo_folder
    repo_out_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup per-commit details directory (enabled by default)
    debug_dir = None
    if save_details:
        debug_dir = repo_out_dir / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Saving per-commit details to %s", debug_dir)
    
    # Clone or update repo
    logger.info("Cloning/updating repository...")
    try:
        repo_dir = clone_or_update_repo(
            repo_url or repo_name,
            repo_cache,
            shallow=not no_shallow,
        )
    except Exception as e:
        logger.error("Failed to clone repo: %s", e)
        return {"status": "error", "message": f"Clone failed: {e}"}
    
    logger.info("Repo ready at %s", repo_dir)
    
    # Get default branch HEAD for filtering
    try:
        branch_name, head_sha = get_default_branch_head(repo_dir)
        logger.info("Default branch: %s (%s)", branch_name, head_sha[:8])
    except Exception as e:
        logger.warning("Could not determine default branch: %s", e)
        head_sha = None
    
    # Load checkpoint if exists
    checkpoint = {}
    if checkpoint_file and checkpoint_file.exists():
        try:
            checkpoint = json.loads(checkpoint_file.read_text())
            logger.info("Loaded checkpoint with %d completed commits", len(checkpoint.get("completed", [])))
        except Exception:
            checkpoint = {}
    
    completed_shas = set(checkpoint.get("completed", []))
    
    # Analyze commits
    debt_results = []
    lifecycle_results = []
    destiny_results = []
    skipped_not_ancestor = 0
    skipped_completed = 0
    errors = 0
    
    total = len(commits)
    start_time = time.time()
    
    for i, commit in enumerate(commits, 1):
        sha = commit.get("sha")
        ai_tool = commit.get("ai_tool") or commit.get("tool", "unknown")
        
        if not sha:
            logger.warning("Commit missing SHA, skipping")
            continue
        
        # Skip if already completed
        if sha in completed_shas:
            skipped_completed += 1
            continue
        
        # Ensure commit is available locally
        try:
            ensure_commit(repo_dir, sha)
        except Exception as e:
            logger.warning("Could not fetch commit %s: %s", sha[:8], e)
            errors += 1
            continue
        
        # Check if commit is ancestor of HEAD (on main branch)
        # Skip this check if include_all_commits is True (default)
        if not include_all_commits and head_sha:
            try:
                if not is_ancestor(repo_dir, sha, head_sha):
                    skipped_not_ancestor += 1
                    continue
            except Exception:
                pass  # Proceed anyway if check fails
        
        # Log progress
        elapsed = time.time() - start_time
        rate = i / elapsed if elapsed > 0 else 0
        eta = (total - i) / rate if rate > 0 else 0
        logger.info(
            "[%d/%d] Analyzing commit %s (%s) - %.1f commits/min, ETA: %.1f min",
            i, total, sha[:8], ai_tool, rate * 60, eta / 60
        )
        
        # Analyze commit
        try:
            # 1. Debt Analysis (always run)
            debt_result = analyze_commit_debt(
                repo_dir=repo_dir,
                sha=sha,
                ai_tool=ai_tool,
                repo_name=repo_name,
                debug=save_details,
                sonarqube_only=sonarqube_only,
                workers=workers,
            )
            debt_results.append(debt_result)
            completed_shas.add(sha)
            
            # 2. Lifecycle Analysis (ALWAYS RUN - core research metric)
            # Tracks file survival, churn, fixes, refactoring after AI commits.
            # Previously gated behind deep_scan flag, but this is essential for
            # the dashboard's "File Stability" and "File Lifecycle Timeline" sections.
            lifecycle_result = None
            if head_sha:
                try:
                    lifecycle_result = analyze_commit_lifecycle(
                        repo_dir=repo_dir,
                        sha=sha,
                        ai_tool=ai_tool,
                        default_head=head_sha,
                        repo_name=repo_name,
                        debug=save_details,
                    )
                except Exception as e:
                    logger.warning("Lifecycle analysis failed for %s: %s", sha[:8], e)
            
            # 3. Destiny Analysis (ALWAYS RUN - Code Survival)
            # Tracks syntactic line survival (git blame)
            # This is distinct from deep_scan (CodeQL/SonarQube) which is optional
            destiny_result = None
            try:
                destiny_result = analyze_code_destiny(
                    repo_dir=repo_dir,
                    sha=sha,
                    debug=save_details,
                )
            except Exception as e:
                logger.warning("Destiny analysis failed for %s: %s", sha[:8], e)
            
            # Collect lifecycle and destiny results for output files
            if lifecycle_result:
                lifecycle_results.append(lifecycle_result)
            if destiny_result:
                # Add repo info for dashboard cross-referencing
                destiny_result["repo"] = repo_name
                destiny_results.append(destiny_result)
            
            # Save per-commit detail file if enabled
            if debug_dir:
                commit_debug_file = debug_dir / f"{sha[:8]}_{ai_tool}.json"
                try:
                    commit_debug_data = {
                        "commit_hash": sha,
                        "repo": repo_name,
                        "ai_tool": ai_tool,
                        "url": commit.get("url", ""),
                        "author": commit.get("author", ""),
                        "message": commit.get("message", "")[:500] if commit.get("message") else "",
                        "timestamp": commit.get("commit_date") or commit.get("date", ""),
                    }
                    
                    # Add debt debug info
                    if debt_result.get("_debug"):
                        commit_debug_data["debt_debug"] = debt_result["_debug"]
                    
                    # Add lifecycle debug info (deep scan)
                    if lifecycle_result and lifecycle_result.get("_debug"):
                        commit_debug_data["lifecycle_debug"] = lifecycle_result["_debug"]
                    
                    # Add destiny debug info
                    if destiny_result and destiny_result.get("file_details"):
                        commit_debug_data["destiny_debug"] = destiny_result["file_details"]
                    
                    # Add summary analysis
                    commit_debug_data["analysis_summary"] = {
                        "debt": {
                            "issues_introduced": debt_result.get("summary", {}).get("total_issues_introduced", 0),
                            "issues_fixed": debt_result.get("summary", {}).get("total_issues_fixed", 0),
                        }
                    }
                    
                    if lifecycle_result:
                        commit_debug_data["analysis_summary"]["lifecycle"] = {
                            "files_analyzed": lifecycle_result.get("code_files_analyzed", 0),
                            "files": lifecycle_result.get("files", []),
                        }
                    
                    if destiny_result:
                        commit_debug_data["analysis_summary"]["destiny"] = {
                            "survival_rate": destiny_result.get("survival_rate", 0),
                            "semantic_survival_rate": destiny_result.get("semantic_survival_rate", 0),
                            "developer_valuation": destiny_result.get("developer_valuation", ""),
                            "lines_added": destiny_result.get("total_lines_added", 0),
                            "lines_still_exist": destiny_result.get("lines_still_exist", 0),
                        }
                    
                    commit_debug_file.write_text(json.dumps(commit_debug_data, indent=2))
                except Exception as e:
                    logger.warning("Could not save debug file for %s: %s", sha[:8], e)
            
            # Save checkpoint periodically
            if checkpoint_file and i % 10 == 0:
                checkpoint["completed"] = list(completed_shas)
                checkpoint_file.write_text(json.dumps(checkpoint))
        except Exception as e:
            logger.error("Error analyzing commit %s: %s", sha[:8], e)
            errors += 1
    
    # Save final checkpoint
    if checkpoint_file:
        checkpoint["completed"] = list(completed_shas)
        checkpoint_file.write_text(json.dumps(checkpoint))
    
    # Save debt results
    debt_file = repo_out_dir / "debt_metrics.json"
    save_results(debt_file, debt_results)
    logger.info("Saved debt metrics to %s", debt_file)
    
    # Save lifecycle results (File Stability Analysis in dashboard)
    lifecycle_file = repo_out_dir / "lifecycle_metrics.json"
    save_results(lifecycle_file, lifecycle_results)
    logger.info("Saved lifecycle metrics to %s (%d commits)", lifecycle_file, len(lifecycle_results))
    
    # Save destiny results (Code Survival / File Destiny in dashboard)
    destiny_file = repo_out_dir / "destiny_metrics.json"
    save_results(destiny_file, destiny_results)
    logger.info("Saved destiny metrics to %s (%d commits)", destiny_file, len(destiny_results))
    
    # ========== ISSUE SURVIVAL ANALYSIS ==========
    # Extract all issues from debt results and check if they still exist at HEAD
    # This is the key research metric: "Do AI-introduced issues survive over time?"
    issue_survival_result = None
    if debt_results:
        logger.info("Running issue survival analysis...")
        
        # Flatten all issues from debt results into the format expected by issue_survival
        all_issues_for_survival = []
        for debt_result in debt_results:
            commit_sha = debt_result.get("commit_hash", "")
            for file_result in debt_result.get("files", []):
                file_path = file_result.get("file_path", "")
                filter_context = file_result.get("issue_filter_context_after", {})
                for issue in file_result.get("issues_added", []):
                    all_issues_for_survival.append({
                        "commit_sha": commit_sha,
                        "file_path": file_path,
                        "filter_context": filter_context,
                        "line": issue.get("line", 0),
                        "rule_id": issue.get("symbol") or issue.get("rule") or issue.get("type", "unknown"),
                        "type": issue.get("type", "unknown"),
                        "severity": issue.get("severity", "unknown"),
                        "message": issue.get("message", ""),
                    })
        
        if all_issues_for_survival:
            try:
                issue_survival_result = analyze_issue_survival(
                    repo_dir=repo_dir,
                    commit_issues=all_issues_for_survival,
                )
                
                # Save issue survival results
                survival_file = repo_out_dir / "issue_survival.json"
                save_results(survival_file, issue_survival_result)
                logger.info(
                    "Issue Survival: %d/%d issues still exist at HEAD (%.1f%% survival rate)",
                    issue_survival_result.get("surviving_issues", 0),
                    issue_survival_result.get("total_issues", 0),
                    issue_survival_result.get("survival_rate", 0) * 100
                )
            except Exception as e:
                logger.warning("Issue survival analysis failed: %s", e)
    
    # Calculate summary statistics
    total_introduced = sum(
        r.get("summary", {}).get("total_issues_introduced", 0)
        for r in debt_results
    )
    total_fixed = sum(
        r.get("summary", {}).get("total_issues_fixed", 0)
        for r in debt_results
    )
    
    summary = {
        "status": "success",
        "repo": repo_name,
        "commits_analyzed": len(debt_results),
        "commits_skipped_not_on_main": skipped_not_ancestor,
        "commits_skipped_already_done": skipped_completed,
        "errors": errors,
        "total_issues_introduced": total_introduced,
        "total_issues_fixed": total_fixed,
        "net_debt_change": total_introduced - total_fixed,
        "output_dir": str(repo_out_dir),
        "save_details": save_details,
        "deep_scan_enabled": deep_scan,
        "debug_dir": str(debug_dir) if debug_dir else None,
    }
    
    # Add issue survival metrics to summary (key research metric)
    if issue_survival_result:
        summary["issue_survival"] = {
            "total_issues": issue_survival_result.get("total_issues", 0),
            "surviving_issues": issue_survival_result.get("surviving_issues", 0),
            "fixed_issues": issue_survival_result.get("fixed_issues", 0),
            "survival_rate": issue_survival_result.get("survival_rate", 0),
        }
    
    # Save summary
    summary_file = repo_out_dir / "summary.json"
    save_results(summary_file, summary)
    
    # Update repos manifest
    repos_manifest = out_dir / "repos.json"
    existing_repos = []
    if repos_manifest.exists():
        try:
            existing_repos = json.loads(repos_manifest.read_text())
        except Exception:
            pass
    if repo_folder not in existing_repos:
        existing_repos.append(repo_folder)
        repos_manifest.write_text(json.dumps(existing_repos, indent=2))
    
    return summary


def main(argv: List[str] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run AI commit analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input JSON file with AI commits",
    )
    parser.add_argument(
        "--out-dir", "-o",
        default=str(OUT_DIR),
        help=f"Output directory (default: {OUT_DIR})",
    )
    parser.add_argument(
        "--repo-cache",
        default=str(REPO_CACHE_DIR),
        help=f"Repository cache directory (default: {REPO_CACHE_DIR})",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Checkpoint file for resuming",
    )
    parser.add_argument(
        "--no-shallow",
        action="store_true",
        help="Clone full repo (not shallow)",
    )
    parser.add_argument(
        "--not-save-details",
        action="store_true",
        help="Disable per-commit detail files (debug/)",
    )
    # Backward compatibility (now ignored, details are on by default)
    parser.add_argument(
        "--debug",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--sonarqube-only",
        action="store_true",
        help="Use only SonarQube for analysis",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max commits to analyze (0 = all)",
    )
    parser.add_argument(
        "--deep-scan",
        action="store_true",
        help="Run extended analysis (e.g., lifecycle)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    
    args = parser.parse_args(argv)
    
    setup_logging(args.log_level)
    
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return 1
    
    out_dir = Path(args.out_dir)
    repo_cache = Path(args.repo_cache)
    checkpoint_file = Path(args.checkpoint) if args.checkpoint else None
    
    # Ensure directories exist
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_cache.mkdir(parents=True, exist_ok=True)
    
    summary = analyze_repo_commits(
        input_file=input_path,
        out_dir=out_dir,
        repo_cache=repo_cache,
        checkpoint_file=checkpoint_file,
        no_shallow=args.no_shallow,
        save_details=not args.not_save_details,
        sonarqube_only=args.sonarqube_only,
        workers=args.workers,
        limit=args.limit,
        deep_scan=args.deep_scan,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"  Repo: {summary.get('repo', 'unknown')}")
    print(f"  Commits analyzed: {summary.get('commits_analyzed', 0)}")
    print(f"  Issues introduced: +{summary.get('total_issues_introduced', 0)}")
    print(f"  Issues fixed: -{summary.get('total_issues_fixed', 0)}")
    print(f"  Net debt change: {summary.get('net_debt_change', 0)}")
    print(f"  Output: {summary.get('output_dir', out_dir)}")
    if summary.get("debug_dir"):
        print(f"  Per-commit details: {summary.get('debug_dir')}")
    else:
        print("  Per-commit details: (disabled)")
    print("=" * 60)
    
    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
