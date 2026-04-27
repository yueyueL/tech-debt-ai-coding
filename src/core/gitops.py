"""
Git operations for the AI code analysis tool.
"""
import logging
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple, Set, List


logger = logging.getLogger(__name__)


# Default timeouts for git operations (in seconds)
GIT_TIMEOUT_DEFAULT = 60  # Most operations
GIT_TIMEOUT_CLONE = 300   # Clone can take longer
GIT_TIMEOUT_FETCH = 120   # Fetch with full history


def run_git(
    args: list[str], 
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None
) -> str:
    """
    Run a git command with timeout protection.
    
    Args:
        args: Git command arguments (e.g., ["log", "-1"])
        cwd: Working directory
        timeout: Override default timeout (seconds). None = auto-detect based on command.
    
    Returns:
        stdout of the git command
        
    Raises:
        RuntimeError: If command fails or times out
    """
    cmd = ["git"] + args
    logger.debug("git %s", " ".join(args))
    
    # Auto-detect timeout based on command type
    if timeout is None:
        if args and args[0] == "clone":
            timeout = GIT_TIMEOUT_CLONE
        elif args and args[0] == "fetch":
            timeout = GIT_TIMEOUT_FETCH
        else:
            timeout = GIT_TIMEOUT_DEFAULT
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Git command timed out after {timeout}s: {' '.join(cmd)}\n"
            "Consider increasing timeout or checking network connectivity."
        )
    
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{stderr}")
    return result.stdout


def _normalize_repo_url(full_name: str) -> str:
    if full_name.startswith(("http://", "https://", "git@")):
        return full_name
    if Path(full_name).exists():
        return full_name
    return f"https://github.com/{full_name}.git"


def _repo_dir_name(full_name: str) -> str:
    if Path(full_name).exists():
        return str(Path(full_name).name)
    name = full_name.strip()
    if name.startswith("git@"):
        path = name.split(":", 1)[1]
        if path.endswith(".git"):
            path = path[:-4]
        return path
    if name.startswith(("http://", "https://")):
        parts = name.split("://", 1)[1]
        if "/" in parts:
            host, rest = parts.split("/", 1)
        else:
            host, rest = parts, ""
        if rest.endswith(".git"):
            rest = rest[:-4]
        if host.endswith("github.com") and rest:
            segments = rest.strip("/").split("/")
            if len(segments) >= 2:
                return f"{segments[0]}/{segments[1]}"
        slug = rest.strip("/") or host
        slug = slug.replace(":", "_").replace("/", "_")
        return slug
    return name


def clone_or_update_repo(full_name: str, dest_dir: Path, shallow: bool = True) -> Path:
    dest_dir = Path(dest_dir)
    if Path(full_name).exists():
        repo_dir = Path(full_name)
        logger.info("Using existing repo at %s", repo_dir)
        return repo_dir

    repo_dir = dest_dir / _repo_dir_name(full_name)
    repo_dir.parent.mkdir(parents=True, exist_ok=True)

    # If a stale/non-git directory exists, remove it to avoid clone failures
    if repo_dir.exists() and not (repo_dir / ".git").exists():
        logger.warning("Removing stale repo directory (no .git): %s", repo_dir)
        shutil.rmtree(repo_dir, ignore_errors=True)

    if (repo_dir / ".git").exists():
        logger.info("Updating repo %s", full_name)
        fetch_args = ["fetch", "--prune", "origin"]
        if shallow:
            fetch_args += ["--depth", "1"]
        run_git(fetch_args, cwd=repo_dir)
        return repo_dir

    clone_url = _normalize_repo_url(full_name)
    logger.info("Cloning repo %s into %s", clone_url, repo_dir)
    clone_args = ["clone", "--no-tags", "--filter=blob:none"]
    if shallow:
        clone_args += ["--depth", "1"]
    clone_args += [clone_url, str(repo_dir)]
    try:
        run_git(clone_args)
        return repo_dir
    except RuntimeError as exc:
        # Retry once if directory exists but isn't a git repo (partial clone)
        if repo_dir.exists() and not (repo_dir / ".git").exists():
            logger.warning("Clone failed, removing partial repo dir and retrying: %s", repo_dir)
            shutil.rmtree(repo_dir, ignore_errors=True)
            run_git(clone_args)
            return repo_dir
        raise exc


def get_default_branch_head(repo_dir: Path) -> Tuple[str, str]:
    """
    Get the default branch name and its HEAD SHA.
    
    Falls back to trying main/master if detected branch doesn't exist.
    """
    branch_name = ""
    
    # Try symbolic ref first
    try:
        ref = run_git(
            ["symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=repo_dir,
        ).strip()
        if ref:
            branch_name = ref.rsplit("/", 1)[-1]
    except RuntimeError:
        branch_name = ""

    # Try remote show origin
    if not branch_name:
        try:
            output = run_git(["remote", "show", "origin"], cwd=repo_dir)
            for line in output.splitlines():
                if "HEAD branch:" in line:
                    branch_name = line.split(":", 1)[1].strip()
                    break
        except RuntimeError:
            pass

    # Try to resolve the detected branch
    if branch_name:
        try:
            head_sha = run_git(["rev-parse", f"origin/{branch_name}"], cwd=repo_dir).strip()
            return branch_name, head_sha
        except RuntimeError:
            # Branch doesn't exist on remote, try fallbacks
            logger.warning("Default branch '%s' not found, trying fallbacks", branch_name)

    # Fallback: try common branch names
    for fallback in ["main", "master", "develop", "trunk"]:
        try:
            head_sha = run_git(["rev-parse", f"origin/{fallback}"], cwd=repo_dir).strip()
            logger.info("Using fallback branch '%s'", fallback)
            return fallback, head_sha
        except RuntimeError:
            continue

    # Last resort: use whatever HEAD points to
    try:
        head_sha = run_git(["rev-parse", "HEAD"], cwd=repo_dir).strip()
        branch_name = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir).strip()
        logger.warning("Using local HEAD as fallback: %s", branch_name)
        return branch_name, head_sha
    except RuntimeError:
        pass

    raise RuntimeError("Unable to determine default branch")


def is_ancestor(repo_dir: Path, sha: str, head_sha: str) -> bool:
    cmd = ["git", "merge-base", "--is-ancestor", sha, head_sha]
    result = subprocess.run(
        cmd,
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    stderr = result.stderr.strip()
    raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{stderr}")


def get_commit_parent(repo_dir: Path, sha: str) -> Optional[str]:
    try:
        parent = run_git(["rev-parse", f"{sha}^"], cwd=repo_dir).strip()
        return parent or None
    except RuntimeError as exc:
        message = str(exc).lower()
        if "unknown revision" in message or "bad revision" in message:
            return None
        if "needed a single revision" in message:
            return None
        if "ambiguous argument" in message:
            return None
        try:
            output = run_git(["cat-file", "-p", sha], cwd=repo_dir)
        except RuntimeError:
            return None
        for line in output.splitlines():
            if line.startswith("parent "):
                return line.split(" ", 1)[1].strip() or None
        return None


def get_commit_timestamp(repo_dir: Path, sha: str) -> Optional[int]:
    """Get Unix timestamp for a commit."""
    try:
        output = run_git(["show", "-s", "--format=%ct", sha], cwd=repo_dir).strip()
    except RuntimeError:
        return None
    if not output:
        return None
    try:
        return int(output)
    except ValueError:
        return None


def ensure_commit(repo_dir: Path, sha: str) -> None:
    """Ensure a commit is available locally, fetching if needed."""
    try:
        run_git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo_dir)
        return
    except RuntimeError:
        pass
    run_git(["fetch", "--no-tags", "origin", sha], cwd=repo_dir)


def list_commit_files(repo_dir: Path, sha: str) -> list[str]:
    """List files changed in a commit."""
    output = run_git(
        ["diff-tree", "--root", "-r", "--name-only", sha],
        cwd=repo_dir,
    )
    files = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip the commit SHA that appears in the first line of diff-tree output
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            continue
        files.append(line)
    return files


def get_commit_diff(repo_dir: Path, sha: str) -> str:
    """Get the diff for a specific commit."""
    parent = get_commit_parent(repo_dir, sha)
    if parent:
        return run_git(["diff", parent, sha], cwd=repo_dir)
    # For root commits, use show
    return run_git(["show", "--format=", sha], cwd=repo_dir)


def get_commit_author(repo_dir: Path, sha: str) -> tuple[str, str]:
    """
    Get author name and email for a commit.
    
    Returns (author_name, author_email)
    """
    try:
        output = run_git(
            ["show", "-s", "--format=%an%x1f%ae", sha],
            cwd=repo_dir,
        ).strip()
    except RuntimeError:
        return "", ""
    
    parts = output.split("\x1f")
    if len(parts) != 2:
        return "", ""
    return parts[0], parts[1]


def get_file_at_commit(repo_dir: Path, sha: str, file_path: str) -> Optional[str]:
    """
    Get file content at a specific commit.
    
    Returns file content as string, or None if file doesn't exist at that commit.
    """
    try:
        content = run_git(
            ["show", f"{sha}:{file_path}"],
            cwd=repo_dir,
        )
        return content
    except RuntimeError:
        return None


def resolve_file_at_head(repo_dir: Path, file_path: str) -> Tuple[Optional[str], str]:
    """
    Get file content at HEAD, following renames if the file was moved.
    
    This is critical for research accuracy: without rename tracking,
    renamed files appear as "deleted", falsely inflating fix/deletion rates.
    
    Returns:
        (content_or_None, resolved_path)
        - If file exists at HEAD under original path: (content, original_path)
        - If file was renamed: (content, new_path)
        - If file was truly deleted: (None, original_path)
    """
    # 1. Try the original path first (most common case)
    content = get_file_at_commit(repo_dir, "HEAD", file_path)
    if content is not None:
        return content, file_path
    
    # 2. File not at original path -- check if it was renamed using git log --follow
    try:
        output = run_git(
            ["log", "--follow", "--diff-filter=R", "--name-status",
             "--format=", "-1", "HEAD", "--", file_path],
            cwd=repo_dir,
            timeout=30,
        )
        # Parse rename entries: "R100\told_path\tnew_path"
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].startswith("R"):
                new_path = parts[2]
                new_content = get_file_at_commit(repo_dir, "HEAD", new_path)
                if new_content is not None:
                    logger.debug("File renamed: %s -> %s", file_path, new_path)
                    return new_content, new_path
    except RuntimeError:
        pass
    
    # 3. Try git log --follow --diff-filter=R with broader search
    try:
        # Look for any rename involving this filename in recent history
        basename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
        output = run_git(
            ["log", "--all", "--format=", "--name-status", "--diff-filter=R",
             "-20", "--", f"*{basename}"],
            cwd=repo_dir,
            timeout=30,
        )
        for line in output.splitlines():
            line = line.strip()
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].startswith("R"):
                old_path, new_path = parts[1], parts[2]
                if old_path == file_path:
                    new_content = get_file_at_commit(repo_dir, "HEAD", new_path)
                    if new_content is not None:
                        logger.debug("File renamed (broad search): %s -> %s", file_path, new_path)
                        return new_content, new_path
    except RuntimeError:
        pass
    
    # 4. Truly deleted
    return None, file_path


def _commit_has_parent_in_object(repo_dir: Path, sha: str) -> bool:
    """
    Check whether the commit object declares a parent, regardless of
    whether that parent is locally reachable.

    Uses `git cat-file -p sha` which reads the raw commit object and
    is always available even in shallow clones.  A `parent <sha>` line
    in the output means the commit is NOT a true root commit.
    """
    try:
        output = run_git(["cat-file", "-p", sha], cwd=repo_dir)
    except RuntimeError:
        return False
    return any(line.startswith("parent ") for line in output.splitlines())


def list_changed_files_with_status(repo_dir: Path, sha: str) -> list[tuple[str, str]]:
    """
    List files changed in a commit with their status.

    Returns list of (file_path, status) tuples.
    Status is: A (added), M (modified), D (deleted), R (renamed), etc.

    IMPORTANT: when get_commit_parent() returns None we must distinguish
    two very different situations:

    1. True root commit (no parent in the commit object at all).
       → `git diff-tree --root` is correct: every file is genuinely new.

    2. Shallow-clone boundary commit.  The commit DECLARES a parent but
       git cannot resolve `SHA^` because the parent is beyond the shallow
       cut-off.  In this case `diff-tree --root` would list the ENTIRE
       repository tree as "Added", falsely attributing thousands of
       pre-existing issues to this one commit.
       → Skip: return [] so the caller produces zero false positives.
    """
    parent = get_commit_parent(repo_dir, sha)
    if parent:
        output = run_git(
            ["diff", "--name-status", parent, sha],
            cwd=repo_dir,
        )
    else:
        # Distinguish true root from shallow-boundary failure.
        if _commit_has_parent_in_object(repo_dir, sha):
            # Parent exists in the commit object but is not locally
            # reachable (shallow clone). Bail out to avoid false attribution.
            logger.warning(
                "Skipping commit %s: parent unreachable (shallow clone boundary). "
                "Re-clone without --depth to analyse this commit.",
                sha[:12],
            )
            return []
        # Genuine root commit — every file in the tree is newly added.
        output = run_git(
            ["diff-tree", "--root", "-r", "--name-status", sha],
            cwd=repo_dir,
        )
    
    files = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip commit SHA in diff-tree output
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            continue
            
        # Parse diff --name-status output
        # Format can be: 
        # M    file.txt
        # R100 old.txt    new.txt
        parts = line.split("\t")
        if len(parts) == 3:
            # Rename: Status, Old Path, New Path
            status = parts[0]
            new_path = parts[2]
            files.append((new_path, status[0]))
        elif len(parts) == 2:
            # Standard: Status, Path
            status, path = parts
            files.append((path, status[0]))  # Take first char of status
            
    return files


def get_changed_lines(repo_dir: Path, sha: str, file_path: str) -> Set[int]:
    """
    Get the set of line numbers changed in the given file for the commit.
    
    Uses `git diff --unified=0` to identify added/modified lines.
    
    Args:
        repo_dir: Repository directory
        sha: Commit SHA
        file_path: Path to the file
        
    Returns:
        Set of line numbers (1-based) that were added or modified.
    """
    parent = get_commit_parent(repo_dir, sha)
    if not parent:
        # Root commit: use `git show` which diffs against the empty tree.
        # This correctly shows all lines as added.
        cmd = ["show", "--unified=0", "--format=", f"{sha}", "--", file_path]
    else:
        cmd = ["diff", "--unified=0", parent, sha, "--", file_path]
        
    try:
        output = run_git(cmd, cwd=repo_dir)
    except RuntimeError:
        return set()
        
    changed_lines = set()
    
    # Parse diff output: @@ -old_start,old_len +new_start,new_len @@
    # Regex to capture the new block header
    hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    
    for line in output.splitlines():
        if line.startswith("@@"):
            match = hunk_header.match(line)
            if match:
                # Group 3 is start line of new block
                # Group 4 is length of new block (default 1 if missing)
                start_line = int(match.group(3))
                length = int(match.group(4)) if match.group(4) else 1
                
                # If length is 0, it's a pure deletion - no new lines to check
                if length == 0:
                    continue
                    
                for i in range(length):
                    changed_lines.add(start_line + i)
                    
    return changed_lines
