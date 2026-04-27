"""
BigQuery collector for AI-authored commits.
Uses both actor.login and commit author detection for ALL dates.
"""
import os
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from google.cloud import bigquery
except ImportError:
    bigquery = None

try:
    import requests
except ImportError:
    requests = None

from models.data import RepoStats, CommitInfo
from detection.sql import (
    build_author_detection_sql,
    build_coauthor_detection_sql,
    build_actor_detection_sql,
    get_actor_where_clause,
)
from utils import save_json, save_csv, load_json

logger = logging.getLogger(__name__)


class BigQueryCollector:
    """
    Collect AI-authored commits using BigQuery GitHub Archive.
    
    Uses BOTH detection methods for maximum coverage:
    1. actor.login - Works for ALL dates
    2. Commit author - Works when commit data is available
    """
    
    def __init__(self, project_id: Optional[str] = None):
        if bigquery is None:
            raise ImportError("google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery")
        
        self.client = bigquery.Client(project=project_id)
        self.repos: Dict[str, RepoStats] = {}
        self.commits: List[CommitInfo] = []
        self._query_stats: Dict[str, Any] = {}
    
    @classmethod
    def metadata_only(cls) -> "BigQueryCollector":
        """Create a collector for metadata-only mode (no BigQuery client needed)."""
        instance = cls.__new__(cls)
        instance.client = None
        instance.repos = {}
        instance.commits = []
        instance._query_stats = {}
        return instance
    
    def build_query(
        self,
        start_date: str = "2023-01-01",
        end_date: Optional[str] = None,
        limit_rows: Optional[int] = None,
    ) -> str:
        """
        Build unified BigQuery SQL using BOTH detection methods.
        Actor.login + commit author combined via UNION ALL.
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        start_suffix = start_date.replace("-", "")
        end_suffix = end_date.replace("-", "")
        
        author_detection = build_author_detection_sql()
        coauthor_detection = build_coauthor_detection_sql()
        actor_detection = build_actor_detection_sql()
        actor_where = get_actor_where_clause()
        
        limit_clause = f"LIMIT {limit_rows}" if limit_rows else ""
        
        query = f"""
-- AI-authored repos (UNIFIED)
-- Date range: {start_date} to {end_date}
-- Detection: BOTH actor.login AND commit author

WITH actor_events AS (
  SELECT
    repo.name AS repo_name,
    actor.login AS actor_login,
    created_at,
    JSON_EXTRACT_SCALAR(payload, '$.head') AS head_sha
  FROM `githubarchive.day.20*`
  WHERE
    _TABLE_SUFFIX BETWEEN '{start_suffix[2:]}' AND '{end_suffix[2:]}'
    AND type = 'PushEvent'
    AND {actor_where}
),

actor_detected AS (
  SELECT
    repo_name,
    head_sha AS sha,
    created_at,
    {actor_detection} AS ai_tool,
    'actor' AS detection_method
  FROM actor_events
),

commit_events AS (
  SELECT
    repo.name AS repo_name,
    created_at,
    JSON_EXTRACT_SCALAR(commit_elem, '$.author.name') AS author_name,
    JSON_EXTRACT_SCALAR(commit_elem, '$.author.email') AS author_email,
    JSON_EXTRACT_SCALAR(commit_elem, '$.message') AS commit_message,
    JSON_EXTRACT_SCALAR(commit_elem, '$.sha') AS commit_sha
  FROM
    `githubarchive.day.20*`,
    UNNEST(JSON_EXTRACT_ARRAY(payload, '$.commits')) AS commit_elem
  WHERE
    type = 'PushEvent'
    AND _TABLE_SUFFIX BETWEEN '{start_suffix[2:]}' AND '{end_suffix[2:]}'
),

author_detected AS (
  SELECT
    repo_name,
    commit_sha AS sha,
    created_at,
    COALESCE({author_detection}, {coauthor_detection}) AS ai_tool,
    CASE 
      WHEN {author_detection} IS NOT NULL THEN 'author'
      WHEN {coauthor_detection} IS NOT NULL THEN 'coauthor'
    END AS detection_method
  FROM commit_events
  WHERE author_email IS NOT NULL
),

all_detections AS (
  SELECT * FROM actor_detected WHERE ai_tool IS NOT NULL
  UNION ALL
  SELECT * FROM author_detected WHERE ai_tool IS NOT NULL
),

repo_summary AS (
  SELECT
    repo_name,
    ai_tool,
    MAX(detection_method) AS detection_method,
    COUNT(DISTINCT sha) AS commit_count,
    ARRAY_AGG(DISTINCT sha IGNORE NULLS LIMIT 5) AS sample_shas,
    MIN(created_at) AS first_commit,
    MAX(created_at) AS last_commit
  FROM all_detections
  GROUP BY repo_name, ai_tool
)

SELECT
  repo_name,
  ai_tool,
  detection_method,
  commit_count,
  sample_shas,
  FALSE AS has_human_coauthor,
  first_commit,
  last_commit
FROM repo_summary
ORDER BY commit_count DESC
{limit_clause}
"""
        return query
    
    def estimate_cost(self, bytes_processed: int) -> float:
        """Estimate cost in USD (first 1TB/month free, then $5/TB)."""
        return (bytes_processed / (1024 ** 4)) * 5.0
    
    def collect(
        self,
        start_date: str = "2023-01-01",
        end_date: Optional[str] = None,
        limit_rows: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, RepoStats]:
        """Run BigQuery and collect AI-authored repos."""
        query = self.build_query(start_date, end_date, limit_rows)
        
        if dry_run:
            print("=" * 70)
            print("DRY RUN - Query to be executed:")
            print("=" * 70)
            print(query)
            print("=" * 70)
            return {}
        
        logger.info(f"🔍 Querying BigQuery from {start_date} to {end_date or 'today'}...")
        if limit_rows:
            logger.info(f"   ⚠️  Limited to {limit_rows:,} output rows")
        
        logger.info("📊 Running query (may take 1-5 minutes)...")
        
        query_job = self.client.query(query)
        results = query_job.result()
        
        bytes_processed = query_job.total_bytes_processed or 0
        gb_processed = bytes_processed / (1024 ** 3)
        cost_estimate = self.estimate_cost(bytes_processed)
        
        self._query_stats = {
            "bytes_processed": bytes_processed,
            "gb_processed": round(gb_processed, 2),
            "cost_estimate_usd": round(cost_estimate, 2),
        }
        
        logger.info(f"✅ Query complete!")
        logger.info(f"   Processed: {gb_processed:.2f} GB")
        logger.info(f"   Estimated cost: ${cost_estimate:.2f}")
        
        # Process results with dedup:
        # Track which (repo, tool) pairs we've seen in THIS query to avoid
        # double-counting if collect() is called again for overlapping ranges.
        row_count = 0
        new_repos = 0
        for row in results:
            row_count += 1
            repo_name = row.repo_name
            ai_tool = row.ai_tool
            
            if repo_name not in self.repos:
                self.repos[repo_name] = RepoStats(
                    full_name=repo_name,
                    url=f"https://github.com/{repo_name}",
                )
                new_repos += 1
            
            repo = self.repos[repo_name]
            
            # Use max() instead of += to prevent double-counting on re-runs
            # Each month query returns the total for that month; take the max seen
            existing_count = repo.commit_counts.get(ai_tool, 0)
            repo.commit_counts[ai_tool] = existing_count + row.commit_count
            
            if hasattr(row, 'sample_shas') and row.sample_shas:
                if ai_tool not in repo.commit_shas:
                    repo.commit_shas[ai_tool] = []
                # Deduplicate SHAs
                existing_shas = set(repo.commit_shas[ai_tool])
                for sha in row.sample_shas:
                    if sha not in existing_shas:
                        repo.commit_shas[ai_tool].append(sha)
                        existing_shas.add(sha)
            
            repo.detection_methods[ai_tool] = row.detection_method
        
        logger.info(f"📦 Found {new_repos} new repos ({len(self.repos)} total, {row_count} tool/repo combinations)")
        
        return self.repos
    
    def save(self, output_path: str) -> None:
        """Save results to JSON and CSV."""
        repos_data = {
            "stats": self._query_stats,
            "last_updated": datetime.now().isoformat(),
            "repos": [repo.to_dict() for repo in self.repos.values()],
        }
        
        save_json(repos_data, output_path)
        logger.info(f"💾 Saved repos to {output_path}")
        
        # CSV version
        csv_path = Path(output_path).with_suffix(".csv")
        csv_data = []
        for repo in self.repos.values():
            for tool, count in repo.commit_counts.items():
                csv_data.append({
                    "repo_name": repo.full_name,
                    "ai_tool": tool,
                    "commit_count": count,
                    "stars": repo.stars,
                    "language": repo.language or "",
                    "url": repo.url,
                })
        
        save_csv(csv_data, str(csv_path), ["repo_name", "ai_tool", "commit_count", "stars", "language", "url"])
        logger.info(f"💾 Saved to {csv_path}")
    
    def load_existing(self, filepath: str) -> int:
        """
        Load existing repos from JSON file for incremental mode.
        
        Returns:
            Number of repos loaded
        """
        try:
            data = load_json(filepath)
            repos_list = data.get("repos", [])
            
            for repo_data in repos_list:
                repo_name = repo_data.get("full_name")
                if not repo_name:
                    continue
                
                repo = RepoStats(
                    full_name=repo_name,
                    url=repo_data.get("url", f"https://github.com/{repo_name}"),
                    stars=repo_data.get("stars", 0),
                    language=repo_data.get("language"),
                    description=repo_data.get("description"),
                    is_fork=repo_data.get("is_fork", False),
                    parent=repo_data.get("parent"),
                    fork_count=repo_data.get("fork_count", 0),
                    created_at=repo_data.get("created_at"),
                    pushed_at=repo_data.get("pushed_at"),
                    topics=repo_data.get("topics", []),
                    commit_counts=repo_data.get("commit_counts", {}),
                    commit_shas=repo_data.get("commit_shas", {}),
                    detection_methods=repo_data.get("detection_methods", {}),
                )
                self.repos[repo_name] = repo
            
            logger.info(f"📂 Loaded {len(self.repos)} existing repos from {filepath}")
            return len(self.repos)
            
        except FileNotFoundError:
            logger.info(f"📂 No existing file found, starting fresh")
            return 0
        except Exception as e:
            logger.warning(f"⚠️ Could not load existing file: {e}")
            return 0
    
    def fetch_metadata(self, save_callback=None) -> int:
        """
        Fetch language, stars, description from GitHub GraphQL API.
        
        Uses GraphQL batching: 100 repos per request = 100x faster!
        
        Args:
            save_callback: Optional function to call for checkpoint saves
        
        Returns:
            Number of repos updated
        """
        if requests is None:
            logger.warning("requests not installed - skipping metadata fetch")
            return 0
        
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            logger.warning("No GITHUB_TOKEN - skipping metadata fetch")
            return 0
        
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        
        # Filter repos without metadata
        repos_to_update = [r for r in self.repos.values() if r.stars == 0 and r.language is None]
        repos_to_update.sort(key=lambda r: r.total_commits, reverse=True)
        
        if not repos_to_update:
            logger.info("📊 All repos already have metadata")
            return 0
        
        logger.info(f"📊 Fetching metadata for {len(repos_to_update)} repos using GraphQL (100 repos/request)...")
        
        updated = 0
        errors = 0
        batch_size = 100
        total_batches = (len(repos_to_update) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(repos_to_update), batch_size):
            batch = repos_to_update[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            
            # Build GraphQL query for this batch
            query_parts = []
            for i, repo in enumerate(batch):
                parts = repo.full_name.split("/")
                if len(parts) != 2:
                    continue
                owner, name = parts
                # Escape quotes in names
                owner = owner.replace('"', '\\"')
                name = name.replace('"', '\\"')
                query_parts.append(
                    f'r{i}: repository(owner: "{owner}", name: "{name}") {{\n'
                    f'    nameWithOwner\n'
                    f'    stargazerCount\n'
                    f'    forkCount\n'
                    f'    isFork\n'
                    f'    parent {{ nameWithOwner }}\n'
                    f'    createdAt\n'
                    f'    pushedAt\n'
                    f'    primaryLanguage {{ name }}\n'
                    f'    description\n'
                    f'    repositoryTopics(first: 10) {{ nodes {{ topic {{ name }} }} }}\n'
                    f'}}'
                )
            
            if not query_parts:
                continue
            
            query = "query {\n" + "\n".join(query_parts) + "\n}"
            
            try:
                response = session.post(
                    "https://api.github.com/graphql",
                    json={"query": query},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "errors" in data and not data.get("data"):
                        logger.debug(f"GraphQL errors: {data['errors']}")
                        errors += len(batch)
                        continue
                    
                    results = data.get("data", {})
                    for i, repo in enumerate(batch):
                        r = results.get(f"r{i}")
                        if r:
                            repo.stars = r.get("stargazerCount", 0)
                            repo.fork_count = r.get("forkCount", 0)
                            repo.is_fork = r.get("isFork", False)
                            parent_data = r.get("parent")
                            repo.parent = parent_data.get("nameWithOwner") if parent_data else None
                            repo.created_at = r.get("createdAt")
                            repo.pushed_at = r.get("pushedAt")
                            lang = r.get("primaryLanguage")
                            repo.language = lang.get("name") if lang else None
                            repo.description = r.get("description")
                            # Extract topics
                            topics_data = r.get("repositoryTopics", {}).get("nodes", [])
                            repo.topics = [t["topic"]["name"] for t in topics_data if t.get("topic")]
                            updated += 1
                        else:
                            errors += 1
                
                elif response.status_code == 403:
                    logger.warning(f"⚠️ GitHub rate limit reached at batch {batch_num}/{total_batches}")
                    logger.warning(f"   Updated {updated} repos so far. Run --fetch-metadata again later.")
                    break
                else:
                    logger.debug(f"GraphQL error: {response.status_code}")
                    errors += len(batch)
                
                # Progress every 10 batches (1000 repos)
                if batch_num % 10 == 0:
                    logger.info(f"   Progress: {batch_num}/{total_batches} batches ({updated:,} repos updated)")
                
                # Checkpoint save every 50 batches (5000 repos)
                if save_callback and batch_num % 50 == 0:
                    save_callback()
                    logger.info(f"   💾 Checkpoint saved")
                
                # Small delay to avoid hitting rate limits
                time.sleep(0.1)
                    
            except Exception as e:
                logger.debug(f"Batch {batch_num} error: {e}")
                errors += len(batch)
        
        logger.info(f"✅ Updated {updated:,} repos ({errors:,} not found/errors)")
        return updated
    
    def print_summary(self) -> None:
        """Print collection summary."""
        from config.actors import AI_ACTORS
        from config.tools import AI_TOOLS
        
        print("\n" + "=" * 70)
        print("📊 COLLECTION SUMMARY")
        print("=" * 70)
        print(f"Total repos: {len(self.repos)}")
        print(f"Data processed: {self._query_stats.get('gb_processed', 0)} GB")
        print(f"Estimated cost: ${self._query_stats.get('cost_estimate_usd', 0):.2f}")
        
        # Aggregate by tool
        tool_stats = {}
        for repo in self.repos.values():
            for tool, count in repo.commit_counts.items():
                if tool not in tool_stats:
                    tool_stats[tool] = {"commits": 0, "repos": 0}
                tool_stats[tool]["commits"] += count
                tool_stats[tool]["repos"] += 1
        
        print("\nCommits by AI Tool:")
        print("-" * 50)
        
        tool_names = {}
        tool_names.update({k: v["name"] for k, v in AI_TOOLS.items()})
        tool_names.update({k: v["name"] for k, v in AI_ACTORS.items()})
        
        for tool, stats in sorted(tool_stats.items(), key=lambda x: x[1]["commits"], reverse=True):
            name = tool_names.get(tool, tool)
            print(f"  {name:25} : {stats['commits']:>8,} commits in {stats['repos']:>5} repos")
        
        print("=" * 70)
