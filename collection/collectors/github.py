"""
GitHub API fetcher for downloading commit diffs.
"""
import os
import time
import logging
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from utils import save_json, load_json

logger = logging.getLogger(__name__)


class GitHubFetcher:
    """
    Fetch actual commit diffs from GitHub API.
    
    Takes commit SHAs from BigQuery results and downloads:
    - Commit metadata
    - File changes with patches
    """
    
    def __init__(self, token: Optional[str] = None):
        if requests is None:
            raise ImportError("requests not installed. Run: pip install requests")
        
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN required. Set environment variable or pass token.")
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0
    
    def _check_rate_limit(self) -> None:
        """Check and wait for rate limit if needed."""
        if self.rate_limit_remaining < 10:
            wait_time = max(0, self.rate_limit_reset - time.time()) + 1
            logger.warning(f"Rate limit low. Waiting {wait_time:.0f}s...")
            time.sleep(wait_time)
    
    def _update_rate_limit(self, response) -> None:
        """Update rate limit info from response headers."""
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 5000))
        self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", 0))
    
    def fetch_commit(
        self,
        repo_name: str,
        sha: str,
        max_files: int = 50,
        max_patch_size: int = 10000,
    ) -> Optional[Dict]:
        """
        Fetch commit details including file diffs.
        
        Args:
            repo_name: "owner/repo" format
            sha: Commit SHA
            max_files: Max files to include
            max_patch_size: Max characters per patch
        
        Returns:
            Commit data dict or None on error
        """
        self._check_rate_limit()
        
        url = f"https://api.github.com/repos/{repo_name}/commits/{sha}"
        
        try:
            response = self.session.get(url, timeout=30)
            self._update_rate_limit(response)
            
            if response.status_code == 404:
                logger.warning(f"Commit not found: {repo_name}/{sha}")
                return None
            
            if response.status_code == 403:
                logger.warning(f"Access denied: {repo_name}/{sha}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Extract relevant fields
            result = {
                "sha": data.get("sha"),
                "repo_name": repo_name,
                "message": data.get("commit", {}).get("message", ""),
                "author": data.get("commit", {}).get("author", {}),
                "committer": data.get("commit", {}).get("committer", {}),
                "stats": data.get("stats", {}),
                "files": [],
            }
            
            # Process files with patches
            for file in data.get("files", [])[:max_files]:
                file_data = {
                    "filename": file.get("filename"),
                    "status": file.get("status"),
                    "additions": file.get("additions", 0),
                    "deletions": file.get("deletions", 0),
                    "changes": file.get("changes", 0),
                }
                
                # Include patch if not too large
                patch = file.get("patch", "")
                if len(patch) <= max_patch_size:
                    file_data["patch"] = patch
                else:
                    file_data["patch"] = f"[TRUNCATED - {len(patch)} chars]"
                
                result["files"].append(file_data)
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Error fetching {repo_name}/{sha}: {e}")
            return None
    
    def fetch_from_repos_json(
        self,
        input_path: str,
        output_path: str,
        max_commits: int = 100,
        max_files_per_commit: int = 50,
    ) -> List[Dict]:
        """
        Fetch commits from BigQuery repos JSON output.
        
        Args:
            input_path: Path to repos JSON from BigQuery collector
            output_path: Path to save commit diffs
            max_commits: Max commits to fetch
            max_files_per_commit: Max files per commit
        
        Returns:
            List of commit data
        """
        data = load_json(input_path)
        repos = data.get("repos", [])
        
        commits_fetched = []
        fetch_count = 0
        
        for repo in repos:
            repo_name = repo.get("full_name")
            commit_shas = repo.get("commit_shas", {})
            
            for tool, shas in commit_shas.items():
                for sha in shas:
                    if fetch_count >= max_commits:
                        break
                    
                    logger.info(f"Fetching {repo_name}/{sha[:7]}...")
                    
                    commit_data = self.fetch_commit(
                        repo_name, sha,
                        max_files=max_files_per_commit,
                    )
                    
                    if commit_data:
                        commit_data["ai_tool"] = tool
                        commits_fetched.append(commit_data)
                        fetch_count += 1
                    
                    # Small delay to be respectful
                    time.sleep(0.1)
                
                if fetch_count >= max_commits:
                    break
            
            if fetch_count >= max_commits:
                break
        
        # Save results
        save_json({"commits": commits_fetched}, output_path)
        logger.info(f"💾 Saved {len(commits_fetched)} commits to {output_path}")
        
        return commits_fetched
