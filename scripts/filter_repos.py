#!/usr/bin/env python3
"""
Filter repos from collect-commits/result by stars and prepare batch input.

This script:
1. Loads star data from data/ai_repos.json
2. Scans collect-commits/result for *_commits.json files
3. Filters repos with stars >= min_stars
4. Creates a batch input file or directory for analysis

Usage:
    python scripts/filter_repos.py --min-stars 50 --output batch_input.json
    python scripts/filter_repos.py --min-stars 100 --list-only
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Paths
ROOT_DIR = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT_DIR / "collect-commits" / "result"
METADATA_FILE = ROOT_DIR / "data" / "ai_repos.json"
DEFAULT_OUTPUT = ROOT_DIR / "data" / "batch_repos.json"


def load_repo_metadata() -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Load repo metadata (stars and language) from ai_repos.json.
    
    Returns:
        (stars_map, language_map): Dicts mapping repo_name.lower() -> value
    """
    stars_map = {}
    language_map = {}
    
    if not METADATA_FILE.exists():
        print(f"Warning: Metadata file not found: {METADATA_FILE}")
        return stars_map, language_map
    
    print(f"Loading repo metadata from {METADATA_FILE}...")
    with open(METADATA_FILE, "r") as f:
        data = json.load(f)
    
    for repo in data.get("repos", []):
        full_name = repo.get("full_name", "")
        if full_name:
            key = full_name.lower()
            stars_map[key] = repo.get("stars", 0)
            language_map[key] = repo.get("language", "")
    
    print(f"  Loaded metadata for {len(stars_map):,} repos")
    return stars_map, language_map


def scan_result_files() -> List[Path]:
    """Scan collect-commits/result for *_commits.json files."""
    if not RESULT_DIR.exists():
        print(f"Error: Result directory not found: {RESULT_DIR}")
        return []
    
    files = list(RESULT_DIR.glob("*_commits.json"))
    print(f"Found {len(files):,} result files in {RESULT_DIR}")
    return files


def extract_repo_name(file_path: Path) -> str:
    """
    Extract repo name from file path.
    
    Example: PostHog_posthog_commits.json -> PostHog/posthog
    """
    name = file_path.stem
    if name.endswith("_commits"):
        name = name[:-8]  # Remove _commits suffix
    
    # Try to load JSON to get actual repo name
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            repo = data.get("repo", "")
            if repo:
                return repo
    except Exception:
        pass
    
    # Fallback: convert underscore to slash (first underscore only)
    parts = name.split("_", 1)
    if len(parts) == 2:
        return f"{parts[0]}/{parts[1]}"
    return name


def filter_repos(
    result_files: List[Path],
    stars_map: Dict[str, int],
    language_map: Dict[str, str],
    min_stars: int = 50,
    languages: List[str] = None,
    max_commits: int = 0,
    min_ai_commits: int = 1,
) -> List[Dict]:
    """
    Filter repos based on criteria.
    
    Args:
        result_files: List of result JSON files
        stars_map: Repo -> stars mapping
        language_map: Repo -> language mapping
        min_stars: Minimum star count
        languages: Optional list of languages to filter
        max_commits: Maximum total commits (0 = no limit)
        min_ai_commits: Minimum AI commits required
        
    Returns:
        List of repo dicts with file path and metadata
    """
    filtered = []
    languages_lower = [l.lower() for l in (languages or [])]
    
    for file_path in result_files:
        repo_name = extract_repo_name(file_path)
        key = repo_name.lower()
        
        # Check stars
        stars = stars_map.get(key, 0)
        if stars < min_stars:
            continue
        
        # Check language
        lang = language_map.get(key, "")
        if languages_lower and lang.lower() not in languages_lower:
            continue
        
        # Load file to check AI commit count
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            
            ai_commits_count = data.get("ai_commits_count", len(data.get("ai_commits", [])))
            total_commits = data.get("total_commits_scanned", 0)
            
            # Check AI commits
            if ai_commits_count < min_ai_commits:
                continue
            
            # Check max commits
            if max_commits > 0 and total_commits > max_commits:
                continue
            
            # Store relative path from project root so it works in Docker too
            try:
                rel_path = file_path.relative_to(ROOT_DIR)
            except ValueError:
                rel_path = file_path
            
            filtered.append({
                "repo": repo_name,
                "file": str(rel_path),
                "stars": stars,
                "language": lang,
                "ai_commits": ai_commits_count,
                "total_commits": total_commits,
                "ai_percentage": round(ai_commits_count / total_commits * 100, 2) if total_commits > 0 else 0,
            })
        except Exception as e:
            print(f"  Warning: Could not load {file_path.name}: {e}")
            continue
    
    # Sort by: ai_commits ascending (fewer first = faster), then stars descending (higher first)
    # This processes faster repos first while prioritizing high-star repos among similar sizes
    filtered.sort(key=lambda x: (x["ai_commits"], -x["stars"]))
    return filtered


def main():
    parser = argparse.ArgumentParser(
        description="Filter repos by stars and prepare for batch analysis"
    )
    parser.add_argument(
        "--min-stars",
        type=int,
        default=50,
        help="Minimum star count (default: 50)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=None,
        help="Filter by languages (e.g., Python TypeScript)",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=0,
        help="Maximum total commits (0 = no limit)",
    )
    parser.add_argument(
        "--min-ai-commits",
        type=int,
        default=1,
        help="Minimum AI commits required (default: 1)",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(DEFAULT_OUTPUT),
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list matching repos, don't write output",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of repos (0 = all)",
    )
    
    args = parser.parse_args()
    
    # Load metadata
    stars_map, language_map = load_repo_metadata()
    
    if not stars_map:
        print("Error: Could not load repo metadata")
        return 1
    
    # Scan result files
    result_files = scan_result_files()
    
    if not result_files:
        print("Error: No result files found")
        return 1
    
    # Filter repos
    filtered = filter_repos(
        result_files=result_files,
        stars_map=stars_map,
        language_map=language_map,
        min_stars=args.min_stars,
        languages=args.languages,
        max_commits=args.max_commits,
        min_ai_commits=args.min_ai_commits,
    )
    
    if args.limit > 0:
        filtered = filtered[:args.limit]
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"FILTER RESULTS (stars >= {args.min_stars})")
    if args.languages:
        print(f"Languages: {', '.join(args.languages)}")
    print(f"{'='*60}")
    print(f"Total repos matching: {len(filtered)}")
    print()
    
    # Print repos
    if args.list_only or len(filtered) <= 50:
        print(f"{'Stars':>8}  {'AI%':>6}  {'AI':>5}  {'Total':>6}  {'Lang':<12}  Repo")
        print("-" * 80)
        for repo in filtered[:100]:
            lang = repo['language'] or "N/A"
            print(f"{repo['stars']:>7,}  {repo['ai_percentage']:>5.1f}%  {repo['ai_commits']:>5}  {repo['total_commits']:>6}  {lang:<12}  {repo['repo']}")
        
        if len(filtered) > 100:
            print(f"... and {len(filtered) - 100} more")
    
    # Save output
    if not args.list_only:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        output_data = {
            "filter_criteria": {
                "min_stars": args.min_stars,
                "languages": args.languages,
                "max_commits": args.max_commits,
                "min_ai_commits": args.min_ai_commits,
            },
            "total_repos": len(filtered),
            "repos": filtered,
        }
        
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\nSaved {len(filtered)} repos to {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
