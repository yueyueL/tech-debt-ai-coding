#!/usr/bin/env python3
"""
Batch analyze multiple repos from filtered list.

This script:
1. Loads filtered repos from batch_repos.json
2. Runs analysis pipeline on each repo (optionally in parallel)
3. Tracks progress and handles errors

Usage:
    python scripts/batch_analyze.py --input data/batch_repos.json
    python scripts/batch_analyze.py --input data/batch_repos.json --parallel 4
"""

import argparse
import json
import logging
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.config import OUT_DIR, REPO_CACHE_DIR
from scripts.run_pipeline import analyze_repo_commits, setup_logging

logger = logging.getLogger(__name__)


def analyze_single_repo(
    repo_info: Dict,
    out_dir: Path,
    repo_cache: Path,
    workers: int,
    limit_commits: int,
    save_details: bool,
    cleanup: bool,
    deep_scan: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """
    Analyze a single repo. This function is designed to run in a separate process.
    
    Returns:
        Tuple of (repo_name, result_dict)
    """
    repo_name = repo_info.get("repo", "unknown")
    input_file = repo_info.get("file", "")
    
    # Setup logging for this process
    setup_logging("INFO")
    proc_logger = logging.getLogger(__name__)
    
    if not input_file or not Path(input_file).exists():
        proc_logger.error("Input file not found: %s", input_file)
        return repo_name, {"status": "error", "message": f"Input file not found: {input_file}"}
    
    # Create per-repo checkpoint
    repo_checkpoint = out_dir / repo_name.replace("/", "_") / "checkpoint.json"
    
    try:
        summary = analyze_repo_commits(
            input_file=Path(input_file),
            out_dir=out_dir,
            repo_cache=repo_cache,
            checkpoint_file=repo_checkpoint,
            no_shallow=False,
            save_details=save_details,
            sonarqube_only=False,
            workers=workers,
            limit=limit_commits,
            include_all_commits=True,  # Analyze all commits, not just those on main branch
            deep_scan=deep_scan,
        )
        
        result = {"repo": repo_name, **summary}
        
        # Cleanup: remove cloned repo to save storage
        if cleanup:
            # Repo is cloned to repo_cache/owner/repo (with forward slash)
            repo_dir = repo_cache / repo_name
            if repo_dir.exists():
                proc_logger.info("Cleaning up: removing %s", repo_dir)
                try:
                    shutil.rmtree(repo_dir)
                except Exception as e:
                    proc_logger.warning("Failed to cleanup %s: %s", repo_dir, e)
            # Also try with underscore format
            repo_dir_alt = repo_cache / repo_name.replace("/", "_")
            if repo_dir_alt.exists() and repo_dir_alt != repo_dir:
                try:
                    shutil.rmtree(repo_dir_alt)
                except Exception:
                    pass
        
        return repo_name, result
        
    except Exception as e:
        proc_logger.error("Error analyzing %s: %s", repo_name, e)
        return repo_name, {"repo": repo_name, "status": "error", "message": str(e)}


def load_batch_input(input_file: Path) -> List[Dict]:
    """Load batch input file with filtered repos."""
    with open(input_file, "r") as f:
        data = json.load(f)
    
    # Support both formats
    if isinstance(data, list):
        return data
    return data.get("repos", [])


def run_batch_analysis(
    repos: List[Dict],
    out_dir: Path,
    repo_cache: Path,
    workers: int = 4,
    limit_commits: int = 0,
    save_details: bool = True,
    resume_from: str = None,
    cleanup: bool = False,
    parallel: int = 1,
    deep_scan: bool = False,
) -> Dict[str, Any]:
    """
    Run analysis on multiple repos.
    
    Args:
        repos: List of repo dicts with 'file' path to JSON
        out_dir: Output directory
        repo_cache: Repo cache directory
        workers: Number of parallel workers per repo (for file analysis)
        limit_commits: Max commits per repo (0 = all)
        save_details: Save per-commit detail files
        resume_from: Resume from specific repo name
        cleanup: If True, remove cloned repo after analysis to save storage
        parallel: Number of repos to process in parallel (1 = sequential)
        deep_scan: If True, run extended analysis (e.g., lifecycle)
        
    Returns:
        Summary dict with overall results
    """
    # Track progress
    checkpoint_file = out_dir / "batch_checkpoint.json"
    checkpoint = {}
    
    if checkpoint_file.exists():
        try:
            checkpoint = json.loads(checkpoint_file.read_text())
            logger.info("Loaded checkpoint with %d completed repos", len(checkpoint.get("completed", [])))
        except Exception:
            checkpoint = {}
    
    completed_repos = set(checkpoint.get("completed", []))
    
    # Skip to resume point
    if resume_from:
        found = False
        for i, repo in enumerate(repos):
            if repo.get("repo") == resume_from:
                repos = repos[i:]
                found = True
                break
        if not found:
            logger.warning("Resume point %s not found, starting from beginning", resume_from)
    
    # Filter out already completed repos
    repos_to_process = []
    for repo_info in repos:
        repo_name = repo_info.get("repo", "unknown")
        if repo_name not in completed_repos:
            repos_to_process.append(repo_info)
        else:
            logger.info("Skipping %s (already completed)", repo_name)
    
    total = len(repos_to_process)
    logger.info("Will process %d repos (parallel=%d)", total, parallel)
    
    results = []
    success_count = 0
    error_count = 0
    start_time = time.time()
    
    if parallel > 1 and total > 1:
        # PARALLEL MODE: Process multiple repos concurrently
        logger.info("=" * 60)
        logger.info("PARALLEL MODE: Processing %d repos with %d workers", total, parallel)
        logger.info("=" * 60)
        
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            # Submit all jobs
            future_to_repo = {}
            for repo_info in repos_to_process:
                future = executor.submit(
                    analyze_single_repo,
                    repo_info,
                    out_dir,
                    repo_cache,
                    workers,
                    limit_commits,
                    save_details,
                    cleanup,
                    deep_scan,
                )
                future_to_repo[future] = repo_info.get("repo", "unknown")
            
            # Process results as they complete
            for future in as_completed(future_to_repo):
                repo_name = future_to_repo[future]
                try:
                    returned_name, result = future.result()
                    results.append(result)
                    
                    if result.get("status") == "success":
                        success_count += 1
                        completed_repos.add(repo_name)
                        logger.info("✓ Completed: %s", repo_name)
                    else:
                        error_count += 1
                        logger.error("✗ Failed: %s - %s", repo_name, result.get("message", ""))
                    
                    # Save checkpoint
                    checkpoint["completed"] = list(completed_repos)
                    checkpoint_file.write_text(json.dumps(checkpoint, indent=2))
                    
                    # Progress update
                    done = success_count + error_count
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    logger.info(
                        "Progress: %d/%d (%.1f%%) | %.1f repos/min | ETA: %.1f min",
                        done, total, done/total*100, rate*60, eta/60
                    )
                    
                except Exception as e:
                    logger.error("Error processing %s: %s", repo_name, e)
                    error_count += 1
                    results.append({"repo": repo_name, "status": "error", "message": str(e)})
    else:
        # SEQUENTIAL MODE: Process repos one at a time
        for i, repo_info in enumerate(repos_to_process, 1):
            repo_name = repo_info.get("repo", "unknown")
            stars = repo_info.get("stars", 0)
            ai_commits = repo_info.get("ai_commits", 0)
            
            # Log progress
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            
            logger.info(
                "\n" + "=" * 60 + 
                f"\n[{i}/{total}] Analyzing {repo_name}"
                f"\n  Stars: {stars:,} | AI Commits: {ai_commits}"
                f"\n  ETA: {eta/60:.1f} min"
                f"\n" + "=" * 60
            )
            
            returned_name, result = analyze_single_repo(
                repo_info, out_dir, repo_cache, workers, limit_commits, save_details, cleanup, deep_scan
            )
            
            results.append(result)
            
            if result.get("status") == "success":
                success_count += 1
                completed_repos.add(repo_name)
            else:
                error_count += 1
            
            # Save checkpoint
            checkpoint["completed"] = list(completed_repos)
            checkpoint["last_repo"] = repo_name
            checkpoint_file.write_text(json.dumps(checkpoint, indent=2))
    
    # Calculate overall summary
    total_introduced = sum(r.get("total_issues_introduced", 0) for r in results)
    total_fixed = sum(r.get("total_issues_fixed", 0) for r in results)
    total_commits = sum(r.get("commits_analyzed", 0) for r in results)
    
    overall_summary = {
        "repos_analyzed": success_count,
        "repos_failed": error_count,
        "total_commits_analyzed": total_commits,
        "total_issues_introduced": total_introduced,
        "total_issues_fixed": total_fixed,
        "net_debt_change": total_introduced - total_fixed,
        "results": results,
    }
    
    # Save overall summary
    summary_file = out_dir / "batch_summary.json"
    summary_file.write_text(json.dumps(overall_summary, indent=2))
    logger.info("Saved batch summary to %s", summary_file)
    
    return overall_summary


def main():
    parser = argparse.ArgumentParser(
        description="Batch analyze repos from filtered list"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Batch input JSON file (from filter_repos.py)",
    )
    parser.add_argument(
        "--out-dir", "-o",
        default=str(OUT_DIR),
        help=f"Output directory (default: {OUT_DIR})",
    )
    parser.add_argument(
        "--repo-cache",
        default=str(REPO_CACHE_DIR),
        help=f"Repo cache directory (default: {REPO_CACHE_DIR})",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel workers per repo (default: 4)",
    )
    parser.add_argument(
        "--limit-repos",
        type=int,
        default=0,
        help="Limit number of repos to analyze (0 = all)",
    )
    parser.add_argument(
        "--limit-commits",
        type=int,
        default=0,
        help="Limit commits per repo (0 = all)",
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
        "--resume-from",
        default=None,
        help="Resume from specific repo name",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove cloned repos after analysis to save storage",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of repos to process in parallel (default: 1 = sequential)",
    )
    parser.add_argument(
        "--deep-scan",
        action="store_true",
        help="Run extended analysis (e.g., lifecycle)",
    )
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        return 1
    
    # Load repos
    repos = load_batch_input(input_path)
    logger.info("Loaded %d repos from %s", len(repos), input_path)
    
    # Apply limit
    if args.limit_repos > 0:
        repos = repos[:args.limit_repos]
        logger.info("Limited to %d repos", len(repos))
    
    out_dir = Path(args.out_dir)
    repo_cache = Path(args.repo_cache)
    
    # Ensure directories exist
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_cache.mkdir(parents=True, exist_ok=True)
    
    # Run batch analysis
    summary = run_batch_analysis(
        repos=repos,
        out_dir=out_dir,
        repo_cache=repo_cache,
        workers=args.workers,
        limit_commits=args.limit_commits,
        save_details=not args.not_save_details,
        resume_from=args.resume_from,
        cleanup=args.cleanup,
        parallel=args.parallel,
        deep_scan=args.deep_scan,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("BATCH ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"  Repos analyzed: {summary['repos_analyzed']}")
    print(f"  Repos failed: {summary['repos_failed']}")
    print(f"  Total commits: {summary['total_commits_analyzed']}")
    print(f"  Issues introduced: +{summary['total_issues_introduced']}")
    print(f"  Issues fixed: -{summary['total_issues_fixed']}")
    print(f"  Net debt change: {summary['net_debt_change']}")
    print(f"  Output: {out_dir}")
    print("=" * 60)
    
    return 0 if summary['repos_failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
