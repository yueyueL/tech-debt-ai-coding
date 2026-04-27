"""
GitHub API commits collector.
"""
import os
import logging
import time
from typing import List, Optional, Generator

from models.data import AICommit, RepoScanResult
from detection.scanner import detect_ai_commit, get_tool_name

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None


class GitHubCommitsCollector:
    """Collect and scan commits from a GitHub repo via API."""
    
    def __init__(self, token: Optional[str] = None):
        if requests is None:
            raise ImportError("requests not installed. Run: pip install requests")
        
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN required.")
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        })
        self.base_url = "https://api.github.com"
    
    def _get_commits_page(self, owner: str, repo: str, page: int = 1, 
                          per_page: int = 100, since: Optional[str] = None,
                          max_retries: int = 5) -> List[dict]:
        """Fetch a page of commits with rate-limit retry."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {"page": page, "per_page": per_page}
        if since:
            params["since"] = since
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
            except Exception as e:
                logger.warning(f"Request error (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(10 * (attempt + 1))
                continue
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                # Use reset header if available, otherwise wait 60s
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                if reset_time > 0:
                    wait = max(0, reset_time - int(time.time())) + 5
                else:
                    wait = 60 * (attempt + 1)
                logger.warning(f"Rate limit hit (attempt {attempt+1}/{max_retries}). Waiting {wait}s...")
                time.sleep(wait)
            elif response.status_code == 404:
                raise ValueError(f"Repository {owner}/{repo} not found")
            elif response.status_code == 422:
                logger.warning(f"Unprocessable: {response.text[:200]}")
                return []
            else:
                logger.warning(f"API error {response.status_code} (attempt {attempt+1}): {response.text[:200]}")
                time.sleep(10 * (attempt + 1))
        
        logger.error(f"Failed to fetch page {page} after {max_retries} retries")
        return []
    
    def iter_commits(self, owner: str, repo: str, 
                     since: Optional[str] = None, 
                     max_commits: Optional[int] = None) -> Generator[dict, None, None]:
        """Iterate through all commits in a repo."""
        page = 1
        total = 0
        
        while True:
            commits = self._get_commits_page(owner, repo, page=page, since=since)
            
            if not commits:
                break
            
            for commit in commits:
                yield commit
                total += 1
                
                if max_commits and total >= max_commits:
                    return
            
            if len(commits) < 100:
                break
            
            page += 1
            
            # Progress log
            if page % 10 == 0:
                logger.info(f"   Fetched {total} commits (page {page})...")
    
    def scan_repo(self, repo_full_name: str, 
                  since: Optional[str] = None,
                  max_commits: Optional[int] = None) -> RepoScanResult:
        """
        Scan a repo for AI-authored commits.
        
        Args:
            repo_full_name: Full repo name like "n8n-io/n8n"
            since: ISO date to start from (e.g., "2024-01-01")
            max_commits: Maximum commits to scan
        
        Returns:
            RepoScanResult with detected AI commits
        """
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo name: {repo_full_name}. Use format 'owner/repo'")
        
        owner, repo = parts
        
        logger.info(f"🔍 Scanning {repo_full_name} for AI commits...")
        
        result = RepoScanResult(repo=repo_full_name, total_commits_scanned=0)
        tools_count = {}
        
        for commit_data in self.iter_commits(owner, repo, since=since, max_commits=max_commits):
            result.total_commits_scanned += 1
            
            # Extract commit info
            commit = commit_data.get("commit", {})
            author = commit.get("author", {})
            sha = commit_data.get("sha", "")
            message = commit.get("message", "")
            
            author_name = author.get("name", "")
            author_email = author.get("email", "")
            date = author.get("date", "")
            
            # GitHub actor (who pushed)
            actor = commit_data.get("author", {})
            actor_login = actor.get("login", "") if actor else ""
            
            # Detect AI - now returns dict with additional info
            detection = detect_ai_commit(
                author_name=author_name,
                author_email=author_email,
                commit_message=message,
                actor_login=actor_login
            )
            
            if detection:
                ai_commit = AICommit(
                    sha=sha,
                    repo=repo_full_name,
                    ai_tool=detection["tool_key"],
                    detection_method=detection["detection_method"],
                    author_name=author_name,
                    author_email=author_email,
                    message=message[:500],  # Truncate long messages
                    date=date,
                    url=f"https://github.com/{repo_full_name}/commit/{sha}",
                    # NEW fields
                    author_role=detection["author_role"],
                    ai_identifier=detection["ai_identifier"],
                    ai_identifier_type=detection["ai_identifier_type"],
                )
                result.ai_commits.append(ai_commit)
                tools_count[detection["tool_key"]] = tools_count.get(detection["tool_key"], 0) + 1
        
        result.tools_found = tools_count
        
        logger.info(f"✅ Scanned {result.total_commits_scanned} commits, found {len(result.ai_commits)} AI commits")
        
        return result
    
    def print_summary(self, result: RepoScanResult) -> None:
        """Print scan results summary."""
        print("\n" + "=" * 70)
        print(f"📊 SCAN RESULTS: {result.repo}")
        print("=" * 70)
        print(f"Total commits scanned: {result.total_commits_scanned:,}")
        print(f"AI commits found: {len(result.ai_commits):,}")
        print()
        
        if result.tools_found:
            print("AI Tools Detected:")
            for tool, count in sorted(result.tools_found.items(), key=lambda x: -x[1]):
                name = get_tool_name(tool)
                print(f"  {name}: {count}")
        
        print("=" * 70)
