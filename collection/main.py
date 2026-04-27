#!/usr/bin/env python3
"""
AI-Code Collector: Discover and analyze AI-authored code from GitHub.

Commands:
  discover  - Find AI-authored repos via BigQuery (GitHub Archive)
  scan      - Deep scan a repo for AI commits (git clone or GitHub API)
  metadata  - Fetch GitHub metadata for existing repos

Examples:
  # Discover AI repos from BigQuery
  python main.py discover --start-date 2024-01-01 --end-date 2024-12-31

  # Scan a specific repo for AI commits
  python main.py scan n8n-io/n8n --git-clone

  # Fetch metadata for discovered repos
  python main.py metadata result/ai_repos.json
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import save_json, load_json, save_csv
from detection.scanner import get_tool_name

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, log_file: str = None):
    """Configure logging with optional file output."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s - %(message)s"
    
    handlers = [logging.StreamHandler()]
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    
    logging.basicConfig(level=level, format=fmt, handlers=handlers)

RESULT_DIR = Path(__file__).resolve().parent / "result"
RESULT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# DISCOVER COMMAND - BigQuery
# =============================================================================

def get_months_in_range(start_date: str, end_date: str) -> list:
    """Get list of (start, end) tuples for each month in range."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    months = []
    current = start.replace(day=1)
    
    while current <= end:
        month_start = max(current, start)
        month_end = min((current + relativedelta(months=1)) - timedelta(days=1), end)
        months.append((month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")))
        current = current + relativedelta(months=1)
    
    return months


def load_completed_months(checkpoint_file: str) -> set:
    """Load set of already-completed months."""
    try:
        data = load_json(checkpoint_file)
        return set(data.get("completed_months", []))
    except (FileNotFoundError, ValueError, KeyError):
        return set()


def save_checkpoint(checkpoint_file: str, completed_months: set):
    """Save completed months to checkpoint file."""
    save_json({"completed_months": list(completed_months)}, checkpoint_file)


def cmd_discover(args):
    """Discover AI-authored repos via BigQuery."""
    from collectors.bigquery import BigQueryCollector
    
    # Check credentials
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   BigQuery may use default credentials or fail")
        print()
    
    try:
        collector = BigQueryCollector(project_id=args.project)
    except ImportError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Load existing repos
    if Path(args.output).exists():
        collector.load_existing(args.output)
    
    # Set default end date
    if not args.end_date:
        args.end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Checkpoint file for tracking progress
    checkpoint_file = str(Path(args.output).with_suffix(".checkpoint.json"))
    
    # Get months to query
    months = get_months_in_range(args.start_date, args.end_date)
    completed_months = load_completed_months(checkpoint_file)
    
    print(f"📅 Date range: {args.start_date} to {args.end_date}")
    print(f"📆 Total months: {len(months)}")
    print(f"✅ Already completed: {len(completed_months)} months")
    print()
    
    # Query month by month
    for i, (month_start, month_end) in enumerate(months):
        month_key = month_start[:7]  # "2024-01"
        
        if month_key in completed_months:
            logger.info(f"⏭️  Skipping {month_key} (already collected)")
            continue
        
        logger.info(f"📅 [{i+1}/{len(months)}] Collecting {month_key}...")
        
        collector.collect(
            start_date=month_start,
            end_date=month_end,
            limit_rows=args.limit,
            dry_run=args.dry_run,
        )
        
        if args.dry_run:
            continue
        
        # Save checkpoint after each month
        completed_months.add(month_key)
        save_checkpoint(checkpoint_file, completed_months)
        collector.save(args.output)
        logger.info(f"💾 Checkpoint saved ({len(collector.repos)} total repos)")
    
    if args.dry_run:
        return
    
    # Fetch metadata at the end
    if os.environ.get("GITHUB_TOKEN") and args.fetch_metadata:
        save_callback = lambda: collector.save(args.output)
        collector.fetch_metadata(save_callback=save_callback)
    
    collector.print_summary()
    collector.save(args.output)
    
    print(f"\n✅ Discovery complete! Results saved to {args.output}")
    print(f"   Checkpoint file: {checkpoint_file}")


# =============================================================================
# SCAN COMMAND - Repo scanning
# =============================================================================

def cmd_scan(args):
    """Scan a GitHub repo for AI-authored commits."""
    # Choose collector
    try:
        if args.git_clone:
            from collectors.git_commits import GitCommitsCollector
            collector = GitCommitsCollector(keep_clone=args.keep_clone)
            logger.info("📦 Using git clone mode (no rate limits)")
        else:
            from collectors.github_commits import GitHubCommitsCollector
            collector = GitHubCommitsCollector()
            logger.info("🌐 Using GitHub API mode")
    except ImportError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Default output path
    if not args.output:
        repo_slug = args.repo.replace("/", "_")
        args.output = str(RESULT_DIR / f"{repo_slug}_commits.json")
    
    # Scan repo
    result = collector.scan_repo(
        repo_full_name=args.repo,
        since=args.since,
        max_commits=args.limit
    )
    
    # Print summary
    collector.print_summary(result)
    
    # Save results
    save_json(result.to_dict(), args.output)
    logger.info(f"💾 Saved {len(result.ai_commits)} AI commits to {args.output}")
    
    # Save CSV version
    csv_path = Path(args.output).with_suffix(".csv")
    csv_data = []
    for commit in result.ai_commits:
        csv_data.append({
            "sha": commit.sha[:12],
            "ai_tool": get_tool_name(commit.ai_tool),
            "detection_method": commit.detection_method,
            "author": commit.author_name,
            "date": commit.date[:10] if commit.date else "",
            "url": commit.url,
            "message": commit.message[:100].replace("\n", " "),
        })
    
    if csv_data:
        save_csv(csv_data, str(csv_path), 
                 ["sha", "ai_tool", "detection_method", "author", "date", "url", "message"])
        logger.info(f"💾 Saved CSV to {csv_path}")
    
    print(f"\n✅ Scan complete! Results saved to {args.output}")


# =============================================================================
# BATCH-SCAN COMMAND - Scan multiple repos from discover results
# =============================================================================

def cmd_batch_scan(args):
    """Batch scan repos for AI-authored commits."""
    from collectors.git_commits import GitCommitsCollector
    
    # Load repos from discover output
    if not Path(args.input).exists():
        print(f"❌ File not found: {args.input}")
        sys.exit(1)
    
    data = load_json(args.input)
    repos_list = data.get("repos", [])
    
    if not repos_list:
        print("❌ No repos found in input file")
        sys.exit(1)
    
    # Filter by minimum stars if specified
    if args.min_stars > 0:
        repos_list = [r for r in repos_list if r.get("stars", 0) >= args.min_stars]
        logger.info(f"📊 {len(repos_list)} repos with >= {args.min_stars} stars")
    
    # Filter by AI tool if specified
    if args.tool:
        repos_list = [r for r in repos_list if args.tool in r.get("commit_counts", {})]
        logger.info(f"📊 {len(repos_list)} repos with {args.tool} commits")
    
    # Sort by total commits descending
    repos_list.sort(key=lambda r: sum(r.get("commit_counts", {}).values()), reverse=True)
    
    # Apply limit
    if args.limit:
        repos_list = repos_list[:args.limit]
    
    # Output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Track progress
    total = len(repos_list)
    success = 0
    failed = 0
    skipped = 0
    
    print(f"📦 Batch scanning {total} repos using git clone...")
    print(f"📂 Output directory: {output_dir}")
    print()
    
    collector = GitCommitsCollector(keep_clone=False)
    
    for i, repo_data in enumerate(repos_list):
        repo_name = repo_data.get("full_name", "")
        if not repo_name:
            continue
        
        repo_slug = repo_name.replace("/", "_")
        output_path = output_dir / f"{repo_slug}_commits.json"
        
        # Skip if already scanned
        if output_path.exists() and not args.force:
            skipped += 1
            logger.info(f"⏭️  [{i+1}/{total}] Skipping {repo_name} (already scanned)")
            continue
        
        logger.info(f"🔍 [{i+1}/{total}] Scanning {repo_name}...")
        
        try:
            result = collector.scan_repo(
                repo_full_name=repo_name,
                since=args.since,
                max_commits=args.max_commits
            )
            
            # Save results
            save_json(result.to_dict(), str(output_path))
            
            # Also save CSV
            csv_path = output_path.with_suffix(".csv")
            csv_data = []
            for commit in result.ai_commits:
                csv_data.append({
                    "sha": commit.sha[:12],
                    "ai_tool": get_tool_name(commit.ai_tool),
                    "detection_method": commit.detection_method,
                    "author": commit.author_name,
                    "date": commit.date[:10] if commit.date else "",
                    "url": commit.url,
                    "message": commit.message[:100].replace("\n", " "),
                })
            
            if csv_data:
                from utils import save_csv
                save_csv(csv_data, str(csv_path),
                         ["sha", "ai_tool", "detection_method", "author", "date", "url", "message"])
            
            success += 1
            logger.info(f"   ✅ {len(result.ai_commits)} AI commits / {result.total_commits_scanned} total")
            
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Failed: {e}")
    
    print()
    print("=" * 70)
    print(f"📊 BATCH SCAN COMPLETE")
    print(f"   Success: {success} | Failed: {failed} | Skipped: {skipped}")
    print(f"   Results in: {output_dir}")
    print("=" * 70)


# =============================================================================
# TOP-SCAN COMMAND - Fetch top GitHub repos and scan for AI commits
# Fills the gap after Oct 2025 when BigQuery lost commit data
# =============================================================================

def _fetch_top_repos_from_github(min_stars: int, pushed_after: str,
                                  language: str = None, max_pages: int = 10,
                                  exclude_repos: set = None) -> list:
    """
    Fetch top-starred repos from GitHub Search API.
    
    GitHub Search returns max 1000 results per query.
    We split by language to get more coverage.
    """
    import requests
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN required for top-scan")
        return []
    
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    
    if exclude_repos is None:
        exclude_repos = set()
    
    # Build search query
    query_parts = [f"stars:>={min_stars}", f"pushed:>={pushed_after}"]
    if language:
        query_parts.append(f"language:{language}")
    query_parts.append("fork:false")  # Exclude forks
    query = " ".join(query_parts)
    
    repos = []
    per_page = 100
    
    for page in range(1, max_pages + 1):
        try:
            resp = session.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc",
                        "per_page": per_page, "page": page},
                timeout=30,
            )
            
            if resp.status_code == 403:
                logger.warning(f"Rate limit hit at page {page}. Waiting 60s...")
                import time
                time.sleep(60)
                continue
            
            if resp.status_code != 200:
                logger.warning(f"Search API error {resp.status_code}: {resp.text[:200]}")
                break
            
            data = resp.json()
            items = data.get("items", [])
            
            if not items:
                break
            
            for item in items:
                full_name = item.get("full_name", "")
                if full_name.lower() not in exclude_repos:
                    repos.append({
                        "full_name": full_name,
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language"),
                        "description": item.get("description"),
                        "url": item.get("html_url", f"https://github.com/{full_name}"),
                        "pushed_at": item.get("pushed_at"),
                        "is_fork": item.get("fork", False),
                    })
            
            total_count = data.get("total_count", 0)
            logger.info(f"   Page {page}: {len(items)} repos (total available: {total_count:,})")
            
            if len(items) < per_page or page * per_page >= min(total_count, 1000):
                break
                
        except Exception as e:
            logger.error(f"Search error on page {page}: {e}")
            break
    
    return repos


def cmd_top_scan(args):
    """
    Fetch top GitHub repos active after Oct 2025 and scan for AI commits.
    
    This fills the gap caused by GitHub removing commit data from
    PushEvents after Oct 7, 2025. BigQuery can only detect actor.login
    after that date, missing repos where AI is author/coauthor.
    """
    import time
    from collectors.git_commits import GitCommitsCollector
    
    if not os.environ.get("GITHUB_TOKEN"):
        print("❌ GITHUB_TOKEN required for top-scan")
        sys.exit(1)
    
    # Load existing discovered repos to avoid re-scanning
    exclude_repos = set()
    existing_data = None
    if args.existing and Path(args.existing).exists():
        existing_data = load_json(args.existing)
        for r in existing_data.get("repos", []):
            exclude_repos.add(r["full_name"].lower())
        logger.info(f"📂 Loaded {len(exclude_repos)} existing repos to skip")
    
    # Languages to search (split queries to bypass 1000 limit per query)
    if args.languages:
        languages = [l.strip() for l in args.languages.split(",")]
    else:
        # Top 15 languages by GitHub repo count
        languages = [
            "Python", "JavaScript", "TypeScript", "Java", "Go",
            "Rust", "C++", "C", "Ruby", "PHP",
            "Swift", "Kotlin", "C#", "Scala", "Shell",
        ]
    
    pushed_after = args.pushed_after
    min_stars = args.min_stars
    
    print(f"🔍 Fetching top GitHub repos (>= {min_stars} stars, pushed after {pushed_after})")
    print(f"   Languages: {', '.join(languages)}")
    print(f"   Excluding {len(exclude_repos)} already-discovered repos")
    print()
    
    # Fetch repos from GitHub Search API
    all_repos = []
    seen = set()
    
    for lang in languages:
        logger.info(f"📋 Searching {lang} repos...")
        repos = _fetch_top_repos_from_github(
            min_stars=min_stars,
            pushed_after=pushed_after,
            language=lang,
            max_pages=args.max_pages,
            exclude_repos=exclude_repos,
        )
        for r in repos:
            key = r["full_name"].lower()
            if key not in seen:
                seen.add(key)
                all_repos.append(r)
        time.sleep(1)  # Be nice to the API
    
    # Also search without language filter for repos not in top-15 languages
    logger.info(f"📋 Searching all-language repos...")
    repos = _fetch_top_repos_from_github(
        min_stars=min_stars,
        pushed_after=pushed_after,
        language=None,
        max_pages=args.max_pages,
        exclude_repos=exclude_repos,
    )
    for r in repos:
        key = r["full_name"].lower()
        if key not in seen:
            seen.add(key)
            all_repos.append(r)
    
    # Sort by stars descending
    all_repos.sort(key=lambda r: r["stars"], reverse=True)
    
    # Apply limit
    if args.limit:
        all_repos = all_repos[:args.limit]
    
    print(f"\n📊 Found {len(all_repos)} repos to scan")
    print()
    
    if not all_repos:
        print("No new repos to scan.")
        return
    
    # Output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Scan each repo via git clone
    collector = GitCommitsCollector(keep_clone=False)
    
    success = 0
    failed = 0
    skipped = 0
    found_ai = 0
    results_summary = []
    total = len(all_repos)
    
    for i, repo_data in enumerate(all_repos):
        repo_name = repo_data["full_name"]
        repo_slug = repo_name.replace("/", "_")
        output_path = output_dir / f"{repo_slug}_commits.json"
        
        # Skip if already scanned
        if output_path.exists() and not args.force:
            skipped += 1
            # Check if it had AI commits
            try:
                existing = load_json(str(output_path))
                if existing.get("ai_commits_count", 0) > 0:
                    found_ai += 1
                    results_summary.append({
                        "full_name": repo_name,
                        "stars": repo_data["stars"],
                        "ai_commits": existing.get("ai_commits_count", 0),
                        "tools": existing.get("tools_found", {}),
                    })
            except:
                pass
            continue
        
        logger.info(f"🔍 [{i+1}/{total}] Scanning {repo_name} ({repo_data['stars']:,} stars)...")
        
        try:
            result = collector.scan_repo(
                repo_full_name=repo_name,
                since=args.since,
                max_commits=args.max_commits,
            )
            
            save_json(result.to_dict(), str(output_path))
            success += 1
            
            if result.ai_commits:
                found_ai += 1
                results_summary.append({
                    "full_name": repo_name,
                    "stars": repo_data["stars"],
                    "ai_commits": len(result.ai_commits),
                    "tools": result.tools_found,
                })
                logger.info(f"   🎯 {len(result.ai_commits)} AI commits found! Tools: {result.tools_found}")
            else:
                logger.info(f"   ⬜ No AI commits in {result.total_commits_scanned} commits scanned")
                
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Failed: {e}")
    
    # Save summary
    summary = {
        "scan_params": {
            "min_stars": min_stars,
            "pushed_after": pushed_after,
            "since": args.since,
            "max_commits": args.max_commits,
            "scanned_at": datetime.now().isoformat(),
        },
        "stats": {
            "total_repos": total,
            "scanned": success,
            "failed": failed,
            "skipped": skipped,
            "with_ai_commits": found_ai,
        },
        "repos_with_ai": sorted(results_summary, key=lambda r: r["ai_commits"], reverse=True),
    }
    
    summary_path = output_dir / "top_scan_summary.json"
    save_json(summary, str(summary_path))
    
    print()
    print("=" * 70)
    print(f"📊 TOP-SCAN COMPLETE")
    print(f"   Scanned: {success} | Failed: {failed} | Skipped: {skipped}")
    print(f"   Repos with AI commits: {found_ai}")
    print(f"   Results: {output_dir}")
    print(f"   Summary: {summary_path}")
    print("=" * 70)
    
    if results_summary:
        print(f"\n🎯 Top repos with AI commits:")
        for r in sorted(results_summary, key=lambda x: x["ai_commits"], reverse=True)[:20]:
            tools_str = ", ".join(f"{t}:{c}" for t, c in sorted(r["tools"].items(), key=lambda x: -x[1]))
            print(f"   {r['full_name']:40} {r['stars']:>8,} stars | {r['ai_commits']:>5} AI commits | {tools_str}")


# =============================================================================
# METADATA COMMAND
# =============================================================================

def cmd_metadata(args):
    """Fetch GitHub metadata for existing repos."""
    from collectors.bigquery import BigQueryCollector
    
    if not os.environ.get("GITHUB_TOKEN"):
        print("❌ GITHUB_TOKEN required for metadata fetching")
        sys.exit(1)
    
    # Create metadata-only collector (no BigQuery client needed)
    collector = BigQueryCollector.metadata_only()
    
    if Path(args.input).exists():
        collector.load_existing(args.input)
    else:
        print(f"❌ File not found: {args.input}")
        sys.exit(1)
    
    if collector.repos:
        output_path = args.output or args.input
        save_callback = lambda: collector.save(output_path)
        collector.fetch_metadata(save_callback=save_callback)
        collector.save(output_path)
        print(f"✅ Metadata fetch complete! Saved to {output_path}")
    else:
        print("❌ No repos to update. Run discover first.")


# =============================================================================
# DEDUPE-FORKS COMMAND
# =============================================================================

def cmd_dedupe_forks(args):
    """Filter out forks from discover results, keeping only originals."""
    if not Path(args.input).exists():
        print(f"❌ File not found: {args.input}")
        sys.exit(1)
    
    data = load_json(args.input)
    repos = data.get("repos", [])
    total = len(repos)
    
    # Count repos with metadata
    has_metadata = sum(1 for r in repos if r.get("is_fork") is not None and r.get("stars", 0) > 0 or r.get("language"))
    no_metadata = total - has_metadata
    
    if no_metadata > total * 0.5:
        print(f"⚠️  {no_metadata}/{total} repos lack metadata (is_fork unknown)")
        print("   Run 'metadata' command first to fetch fork info")
        print()
    
    # Filter forks
    min_stars = args.min_stars
    kept = []
    removed_forks = 0
    removed_stars = 0
    
    for r in repos:
        is_fork = r.get("is_fork", False)
        stars = r.get("stars", 0)
        
        if is_fork:
            # Keep fork ONLY if it has significant stars on its own
            if stars >= min_stars:
                kept.append(r)
            else:
                removed_forks += 1
        else:
            kept.append(r)
    
    # Also filter by minimum stars if requested
    if args.filter_stars and args.filter_stars > 0:
        before = len(kept)
        kept = [r for r in kept if r.get("stars", 0) >= args.filter_stars]
        removed_stars = before - len(kept)
    
    print(f"📊 Fork deduplication results:")
    print(f"   Total repos:        {total:>10,}")
    print(f"   Forks removed:      {removed_forks:>10,} (forks with < {min_stars} stars)")
    if removed_stars:
        print(f"   Low-star removed:   {removed_stars:>10,} (< {args.filter_stars} stars)")
    print(f"   Repos kept:         {len(kept):>10,}")
    print()
    
    # Show some examples of removed forks
    fork_examples = [r for r in repos if r.get("is_fork", False) and r.get("stars", 0) < min_stars]
    if fork_examples:
        print(f"   Example forks removed (showing 10):")
        for r in fork_examples[:10]:
            parent = r.get("parent", "?")
            print(f"     {r['full_name']} (fork of {parent}, {r.get('stars', 0)} stars)")
        print()
    
    # Save filtered results
    output_path = args.output or args.input
    data["repos"] = kept
    data["fork_filter"] = {
        "applied": True,
        "min_fork_stars": min_stars,
        "min_stars": args.filter_stars or 0,
        "original_count": total,
        "kept_count": len(kept),
        "forks_removed": removed_forks,
    }
    save_json(data, output_path)
    
    # Also save CSV
    csv_path = Path(output_path).with_suffix(".csv")
    csv_data = []
    for r in kept:
        for tool, count in r.get("commit_counts", {}).items():
            csv_data.append({
                "repo_name": r["full_name"],
                "ai_tool": tool,
                "commit_count": count,
                "stars": r.get("stars", 0),
                "language": r.get("language", ""),
                "is_fork": r.get("is_fork", False),
                "url": r.get("url", ""),
            })
    save_csv(csv_data, str(csv_path),
             ["repo_name", "ai_tool", "commit_count", "stars", "language", "is_fork", "url"])
    
    print(f"✅ Saved {len(kept)} repos to {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Shared parent parser for global options (works before AND after subcommand)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose/debug logging")
    common.add_argument("--log-file", default=None,
                        help="Also log to file (e.g., collect.log)")
    
    parser = argparse.ArgumentParser(
        description="AI-Code Collector: Discover and analyze AI-authored code from GitHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
        parents=[common],
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # === DISCOVER command ===
    discover_parser = subparsers.add_parser(
        "discover", 
        help="Find AI-authored repos via BigQuery (GitHub Archive)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog="""
Examples:
  # Test one month
  python main.py discover --start-date 2024-01-01 --end-date 2024-01-31 --limit 100

  # Full 2024 collection (with monthly checkpoints)
  python main.py discover --start-date 2024-01-01 --end-date 2024-12-31
  
  # Resume interrupted collection
  python main.py discover --start-date 2024-01-01 --end-date 2024-12-31
        """,
    )
    discover_parser.add_argument("--project", default=None,
                                  help="GCP project ID (uses default if not set)")
    discover_parser.add_argument("--start-date", default="2024-01-01",
                                  help="Start date YYYY-MM-DD (default: 2024-01-01)")
    discover_parser.add_argument("--end-date", default=None,
                                  help="End date YYYY-MM-DD (default: today)")
    discover_parser.add_argument("--limit", type=int, default=None,
                                  help="Limit output rows per month (for testing)")
    discover_parser.add_argument("-o", "--output", default=str(RESULT_DIR / "ai_repos.json"),
                                  help="Output file path")
    discover_parser.add_argument("--dry-run", action="store_true",
                                  help="Show query without executing")
    discover_parser.add_argument("--fetch-metadata", action="store_true",
                                  help="Fetch language/stars from GitHub API after collection")
    discover_parser.set_defaults(func=cmd_discover)
    
    # === SCAN command ===
    scan_parser = subparsers.add_parser(
        "scan",
        help="Deep scan a repo for AI commits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog="""
Examples:
  # Scan a repo (uses GitHub API by default)
  python main.py scan n8n-io/n8n
  
  # Use git clone (no rate limits, better for batch processing)
  python main.py scan n8n-io/n8n --git-clone
  
  # With date filter
  python main.py scan Aider-AI/aider --since 2024-01-01
  
  # With output file
  python main.py scan cline/cline -o result/cline_commits.json
  
  # Limit commits (for testing)
  python main.py scan vercel/next.js --limit 1000
        """,
    )
    scan_parser.add_argument("repo", help="GitHub repo in format 'owner/repo'")
    scan_parser.add_argument("--since", default=None,
                              help="Only commits after this date (YYYY-MM-DD)")
    scan_parser.add_argument("--limit", type=int, default=None,
                              help="Max commits to scan (for testing)")
    scan_parser.add_argument("-o", "--output", default=None,
                              help="Output JSON file path")
    scan_parser.add_argument("--git-clone", action="store_true",
                              help="Use git clone instead of GitHub API (no rate limits)")
    scan_parser.add_argument("--keep-clone", action="store_true",
                              help="Keep the cloned repo (only with --git-clone)")
    scan_parser.set_defaults(func=cmd_scan)
    
    # === BATCH-SCAN command ===
    batch_parser = subparsers.add_parser(
        "batch-scan",
        help="Batch scan repos for AI commits (from discover results)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog="""
Examples:
  # Scan top repos from discover output
  python main.py batch-scan result/ai_repos.json

  # Only repos with >= 100 stars
  python main.py batch-scan result/ai_repos.json --min-stars 100

  # Only repos with copilot commits, limit to top 50
  python main.py batch-scan result/ai_repos.json --tool copilot --limit 50

  # Force re-scan of already processed repos
  python main.py batch-scan result/ai_repos.json --force
        """,
    )
    batch_parser.add_argument("input", help="Input JSON file from discover command")
    batch_parser.add_argument("-o", "--output-dir", default=str(RESULT_DIR / "commits"),
                               help="Output directory for scan results")
    batch_parser.add_argument("--min-stars", type=int, default=0,
                               help="Minimum star count to filter repos")
    batch_parser.add_argument("--tool", default=None,
                               help="Only repos with this AI tool (e.g., copilot, claude)")
    batch_parser.add_argument("--limit", type=int, default=None,
                               help="Max repos to scan")
    batch_parser.add_argument("--since", default=None,
                               help="Only commits after this date (YYYY-MM-DD)")
    batch_parser.add_argument("--max-commits", type=int, default=None,
                               help="Max commits to scan per repo")
    batch_parser.add_argument("--force", action="store_true",
                               help="Re-scan repos even if output exists")
    batch_parser.set_defaults(func=cmd_batch_scan)
    
    # === TOP-SCAN command ===
    topscan_parser = subparsers.add_parser(
        "top-scan",
        help="Fetch top GitHub repos and scan for AI commits (fills BigQuery gap after Oct 2025)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog="""
Examples:
  # Scan top repos with >= 500 stars, pushed after Oct 2025
  python main.py top-scan --min-stars 500

  # Exclude repos already in discover results
  python main.py top-scan --existing result/ai_repos.json --min-stars 200

  # Only scan Python and TypeScript repos, top 500
  python main.py top-scan --languages "Python,TypeScript" --limit 500

  # Scan all commits since 2025-10-01 only
  python main.py top-scan --since 2025-10-01 --min-stars 1000

NOTE: GitHub removed commit data from PushEvents on Oct 7, 2025.
This command fills that gap by scanning top repos via git clone.
        """,
    )
    topscan_parser.add_argument("--min-stars", type=int, default=500,
                                 help="Minimum stars for repos to scan (default: 500)")
    topscan_parser.add_argument("--pushed-after", default="2025-10-01",
                                 help="Only repos pushed after this date (default: 2025-10-01)")
    topscan_parser.add_argument("--existing", default=None,
                                 help="Existing ai_repos.json to skip already-discovered repos")
    topscan_parser.add_argument("--languages", default=None,
                                 help="Comma-separated languages to search (default: top 15)")
    topscan_parser.add_argument("--limit", type=int, default=None,
                                 help="Max repos to scan in total")
    topscan_parser.add_argument("--max-pages", type=int, default=10,
                                 help="Max pages per language search (default: 10, 100 repos/page)")
    topscan_parser.add_argument("--since", default=None,
                                 help="Only scan commits after this date (YYYY-MM-DD)")
    topscan_parser.add_argument("--max-commits", type=int, default=5000,
                                 help="Max commits to scan per repo (default: 5000)")
    topscan_parser.add_argument("-o", "--output-dir", default=str(RESULT_DIR / "top-scan"),
                                 help="Output directory for scan results")
    topscan_parser.add_argument("--force", action="store_true",
                                 help="Re-scan repos even if output exists")
    topscan_parser.set_defaults(func=cmd_top_scan)
    
    # === METADATA command ===
    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Fetch GitHub metadata for existing repos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog="""
Examples:
  # Update metadata for discovered repos
  python main.py metadata result/ai_repos.json
  
  # Save to different file
  python main.py metadata result/ai_repos.json -o result/ai_repos_with_metadata.json
        """,
    )
    metadata_parser.add_argument("input", help="Input JSON file from discover command")
    metadata_parser.add_argument("-o", "--output", default=None,
                                  help="Output file path (default: same as input)")
    metadata_parser.set_defaults(func=cmd_metadata)
    
    # === DEDUPE-FORKS command ===
    dedupe_parser = subparsers.add_parser(
        "dedupe-forks",
        help="Filter forks from discover results (keeps originals)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog="""
Examples:
  # Remove forks (keep forks only if >= 100 stars)
  python main.py dedupe-forks result/ai_repos.json

  # Stricter: remove forks with < 500 stars
  python main.py dedupe-forks result/ai_repos.json --min-stars 500

  # Also filter all repos by minimum stars
  python main.py dedupe-forks result/ai_repos.json --filter-stars 10

  # Save to separate file
  python main.py dedupe-forks result/ai_repos.json -o result/ai_repos_clean.json
        """,
    )
    dedupe_parser.add_argument("input", help="Input JSON file from discover command")
    dedupe_parser.add_argument("-o", "--output", default=None,
                                help="Output file path (default: overwrites input)")
    dedupe_parser.add_argument("--min-stars", type=int, default=100,
                                help="Keep forks only if they have >= this many stars (default: 100)")
    dedupe_parser.add_argument("--filter-stars", type=int, default=None,
                                help="Also remove ALL repos below this star count")
    dedupe_parser.set_defaults(func=cmd_dedupe_forks)
    
    # Parse and run
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    setup_logging(verbose=args.verbose, log_file=args.log_file)
    args.func(args)


if __name__ == "__main__":
    main()
