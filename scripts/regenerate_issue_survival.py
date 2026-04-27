#!/usr/bin/env python3
"""
Regenerate issue_survival.json from existing debt_metrics.json
without re-running the full pipeline. Uses the current src/ code.
"""
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics.issue_survival import analyze_issue_survival
from src.core.config import REPO_CACHE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def regenerate_survival(out_dir: Path, repo_cache: Path, limit: int = 0):
    """Regenerate issue_survival.json for all repos in out_dir."""
    repos = sorted([d for d in out_dir.iterdir() if d.is_dir() and (d / "debt_metrics.json").exists()])
    logger.info("Found %d repos with debt_metrics.json in %s", len(repos), out_dir)

    done = 0
    skipped = 0
    errors = 0

    for i, repo_dir_out in enumerate(repos):
        if limit and done >= limit:
            break

        repo_name = repo_dir_out.name.replace("_", "/", 1)
        debt_file = repo_dir_out / "debt_metrics.json"
        survival_file = repo_dir_out / "issue_survival.json"

        # Load debt metrics
        try:
            debt_results = json.loads(debt_file.read_text())
        except Exception as e:
            logger.warning("Failed to load %s: %s", debt_file, e)
            errors += 1
            continue

        if not isinstance(debt_results, list):
            skipped += 1
            continue

        # Flatten issues (same logic as run_pipeline.py line 355-370)
        all_issues = []
        for debt_result in debt_results:
            commit_sha = debt_result.get("commit_hash", "")
            for file_result in debt_result.get("files", []):
                file_path = file_result.get("file_path", "")
                for issue in file_result.get("issues_added", []):
                    all_issues.append({
                        "commit_sha": commit_sha,
                        "file_path": file_path,
                        "line": issue.get("line", 0),
                        "rule_id": issue.get("symbol") or issue.get("rule") or issue.get("type", "unknown"),
                        "type": issue.get("type", "unknown"),
                        "severity": issue.get("severity", "unknown"),
                        "message": issue.get("message", ""),
                    })

        if not all_issues:
            skipped += 1
            continue

        # Find repo clone
        parts = repo_name.split("/")
        repo_clone = repo_cache / parts[0] / parts[1] if len(parts) == 2 else repo_cache / repo_name
        if not repo_clone.exists():
            logger.debug("No repo cache for %s, skipping", repo_name)
            skipped += 1
            continue

        # Run issue survival
        try:
            result = analyze_issue_survival(repo_dir=repo_clone, commit_issues=all_issues)
            survival_file.write_text(json.dumps(result, indent=2, default=str))
            done += 1
            if (done % 10) == 0:
                logger.info("[%d/%d] Regenerated %s (%d tracked, %d surviving)",
                           done, len(repos), repo_name,
                           result.get("total_issues", 0), result.get("surviving_issues", 0))
        except Exception as e:
            logger.warning("Failed survival for %s: %s", repo_name, e)
            errors += 1

    logger.info("Done: %d regenerated, %d skipped, %d errors", done, skipped, errors)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate issue_survival.json from existing debt_metrics")
    parser.add_argument("--out-dir", default="outnew", help="Output directory with repo results")
    parser.add_argument("--repo-cache", default=str(REPO_CACHE_DIR), help="Repo cache directory")
    parser.add_argument("--limit", type=int, default=0, help="Max repos to process (0=all)")
    args = parser.parse_args()

    regenerate_survival(Path(args.out_dir), Path(args.repo_cache), args.limit)
