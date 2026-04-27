"""
Git clone-based commits collector.

No API rate limits - clones repo to tmp/, scans commits, then deletes.
"""
import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Generator

from models.data import AICommit, RepoScanResult
from detection.scanner import detect_ai_commit, get_tool_name

logger = logging.getLogger(__name__)

# Default temp directory for clones
TMP_DIR = Path(__file__).resolve().parent.parent / "tmp"


class GitCommitsCollector:
    """Collect and scan commits by cloning repos locally."""
    
    def __init__(self, clone_dir: Optional[str] = None, keep_clone: bool = False):
        """
        Args:
            clone_dir: Directory to clone repos into (default: ./tmp)
            keep_clone: If True, don't delete clone after scanning
        """
        self.clone_dir = Path(clone_dir) if clone_dir else TMP_DIR
        self.clone_dir.mkdir(parents=True, exist_ok=True)
        self.keep_clone = keep_clone
    
    def _run_git(self, args: List[str], cwd: str, timeout: int = 300) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                logger.warning(f"git {' '.join(args)}: {result.stderr[:200]}")
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error(f"git command timed out: {args}")
            return ""
        except Exception as e:
            logger.error(f"git error: {e}")
            return ""
    
    def _clone_repo(self, repo_url: str, clone_path: Path) -> bool:
        """Clone a repo. Returns True on success."""
        if clone_path.exists():
            shutil.rmtree(clone_path)
        
        logger.info(f"   Cloning {repo_url}...")
        try:
            result = subprocess.run(
                ["git", "clone", "--bare", "--filter=blob:none", repo_url, str(clone_path)],
                capture_output=True,
                text=True,
                timeout=600  # 10 min timeout for large repos
            )
        except subprocess.TimeoutExpired:
            logger.error(f"Clone timed out after 600s: {repo_url}")
            return False
        except Exception as e:
            logger.error(f"Clone error for {repo_url}: {e}")
            return False
        
        if result.returncode != 0:
            logger.error(f"Clone failed: {result.stderr[:200]}")
            return False
        
        return True
    
    def _get_commit_log(self, clone_path: Path, since: Optional[str] = None, 
                        max_commits: Optional[int] = None) -> str:
        """Get formatted commit log."""
        # Format: SHA|author_name|author_email|committer_name|committer_email|date|message
        # Added committer info (%cn, %ce) to detect AI tools that appear as committer
        format_str = "%H|%an|%ae|%cn|%ce|%aI|%s%n%b%n---COMMIT_END---"
        
        # Use --all to include commits from all branches (including orphaned/deleted branches)
        args = ["log", "--all", f"--format={format_str}"]
        
        if since:
            args.append(f"--since={since}")
        
        if max_commits:
            args.append(f"-n{max_commits}")
        
        return self._run_git(args, str(clone_path), timeout=120)
    
    def _parse_commits(self, log_output: str, repo_name: str) -> Generator[dict, None, None]:
        """Parse git log output into commit dicts."""
        if not log_output:
            return
        
        commits = log_output.split("---COMMIT_END---")
        
        for commit_text in commits:
            commit_text = commit_text.strip()
            if not commit_text:
                continue
            
            lines = commit_text.split("\n")
            if not lines:
                continue
            
            # First line has the main info
            first_line = lines[0]
            parts = first_line.split("|", 6)
            
            if len(parts) < 7:
                continue
            
            sha, author_name, author_email, committer_name, committer_email, date, subject = parts
            
            # Rest is the body (including Co-authored-by)
            body = "\n".join(lines[1:]) if len(lines) > 1 else ""
            message = subject + "\n" + body
            
            yield {
                "sha": sha,
                "author_name": author_name,
                "author_email": author_email,
                "committer_name": committer_name,
                "committer_email": committer_email,
                "date": date,
                "message": message,
                "url": f"https://github.com/{repo_name}/commit/{sha}"
            }
    
    def scan_repo(self, repo_full_name: str,
                  since: Optional[str] = None,
                  max_commits: Optional[int] = None) -> RepoScanResult:
        """
        Scan a repo for AI-authored commits by cloning it.
        
        Args:
            repo_full_name: Full repo name like "n8n-io/n8n"
            since: Only commits after this date (e.g., "2024-01-01")
            max_commits: Maximum commits to scan
        
        Returns:
            RepoScanResult with detected AI commits
        """
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo name: {repo_full_name}. Use format 'owner/repo'")
        
        owner, repo = parts
        repo_url = f"https://github.com/{repo_full_name}.git"
        clone_path = self.clone_dir / f"{owner}_{repo}"
        
        logger.info(f"🔍 Scanning {repo_full_name} for AI commits (git clone)...")
        
        result = RepoScanResult(repo=repo_full_name, total_commits_scanned=0)
        tools_count = {}
        
        try:
            # Clone the repo
            if not self._clone_repo(repo_url, clone_path):
                logger.error(f"Failed to clone {repo_full_name}")
                return result
            
            # Get commit log
            log_output = self._get_commit_log(clone_path, since=since, max_commits=max_commits)
            
            # Parse and scan commits
            for commit_data in self._parse_commits(log_output, repo_full_name):
                result.total_commits_scanned += 1
                
                # Detect AI from author first
                detection = detect_ai_commit(
                    author_name=commit_data["author_name"],
                    author_email=commit_data["author_email"],
                    commit_message=commit_data["message"],
                    actor_login=""  # No actor from git log
                )
                
                # If not found, also check committer (for aider-chat-bot, etc.)
                if not detection and commit_data.get("committer_name"):
                    committer_name = commit_data["committer_name"]
                    committer_email = commit_data.get("committer_email", "")
                    # Only check if committer differs from author
                    if committer_name != commit_data["author_name"]:
                        detection = detect_ai_commit(
                            author_name=committer_name,
                            author_email=committer_email,
                            commit_message="",  # Already checked in first pass
                            actor_login=""
                        )
                        if detection:
                            # Mark as committer detection
                            detection["detection_method"] = "committer"
                            detection["ai_identifier_type"] = "committer_" + detection["ai_identifier_type"]
                
                if detection:
                    ai_commit = AICommit(
                        sha=commit_data["sha"],
                        repo=repo_full_name,
                        ai_tool=detection["tool_key"],
                        detection_method=detection["detection_method"],
                        author_name=commit_data["author_name"],
                        author_email=commit_data["author_email"],
                        message=commit_data["message"][:500],
                        date=commit_data["date"],
                        url=commit_data["url"],
                        # NEW fields
                        author_role=detection["author_role"],
                        ai_identifier=detection["ai_identifier"],
                        ai_identifier_type=detection["ai_identifier_type"],
                    )
                    result.ai_commits.append(ai_commit)
                    tools_count[detection["tool_key"]] = tools_count.get(detection["tool_key"], 0) + 1
            
            result.tools_found = tools_count
            
        finally:
            # Clean up clone
            if not self.keep_clone and clone_path.exists():
                logger.info(f"   Cleaning up clone...")
                shutil.rmtree(clone_path, ignore_errors=True)
        
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
