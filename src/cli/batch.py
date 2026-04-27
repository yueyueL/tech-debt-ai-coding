"""
CLI batch operations: batch analyze, deep scan, and clear output.
"""

import json
from pathlib import Path

from src.cli.colors import Colors
from src.cli.config import _prompt, _yes_no
from src.cli.dashboard import _open_dashboard


def _batch_analyze(config: dict) -> None:
    """Batch analyze all repos in a directory."""
    root_dir = Path(__file__).resolve().parents[2]
    default_dir = root_dir / "data" / "claude"

    print(f"\n{Colors.BOLD}📦 Batch Analysis{Colors.ENDC}")
    print(f"{'-' * 40}")
    print(f"Scans a directory for all ai_commit_summary*.json files")
    print(f"and runs the full pipeline on each.\n")

    dir_path = input(f"Directory to scan [{Colors.BLUE}{default_dir}{Colors.ENDC}]: ").strip()
    if not dir_path:
        dir_path = str(default_dir)

    scan_dir = Path(dir_path)
    if not scan_dir.exists():
        print(f"{Colors.RED}Directory not found: {scan_dir}{Colors.ENDC}")
        return

    # Find all AI commit JSON files (various formats)
    patterns = ["ai_commit_summary*.json", "ai_commits*.json", "*_commits.json"]
    files = []
    for pattern in patterns:
        files.extend(scan_dir.glob(pattern))
    # Remove duplicates (in case files match multiple patterns)
    files = list(set(files))

    if not files:
        print(f"{Colors.YELLOW}No ai_commit_summary*.json files found in {scan_dir}{Colors.ENDC}")
        return

    print(f"\n{Colors.GREEN}Found {len(files)} repo files:{Colors.ENDC}")
    for i, f in enumerate(files, 1):
        # Extract repo name from filename
        name = f.stem
        if name.startswith("ai_commit_summary_"):
            name = name.replace("ai_commit_summary_", "")
        elif name.startswith("ai_commits_"):
            name = name.replace("ai_commits_", "")
        elif name.endswith("_commits"):
            name = name.rsplit("_commits", 1)[0]
        print(f"  {i}. {name}")

    confirm = input(f"\n{Colors.BOLD}Analyze all {len(files)} repos? (Y/n): {Colors.ENDC}").strip().lower()
    if confirm == "n":
        print(f"{Colors.YELLOW}Cancelled.{Colors.ENDC}")
        return

    # Run in parallel across repos using the batch runner
    try:
        from scripts.run_parallel import main as run_parallel_main
    except Exception as exc:
        print(f"{Colors.RED}Batch runner not available: {exc}{Colors.ENDC}")
        return

    parallel = config.get("parallel", 4)
    workers = config.get("workers", 4)
    limit = config.get("limit", 0)

    argv = [
        "--input-files",
        *[str(f) for f in files],
        "--out-dir",
        config["out_dir"],
        "--repo-cache",
        config["repo_cache"],
        "--parallel",
        str(parallel),
        "--workers",
        str(workers),
        "--log-level",
        config["log_level"],
    ]
    save_details = config.get("save_details", config.get("debug", True))
    if not save_details:
        argv.append("--not-save-details")
    if limit > 0:
        argv.extend(["--limit", str(limit)])
    if config.get("sonarqube_only"):
        argv.append("--sonarqube-only")
    if config.get("deep_scan"):
        argv.append("--deep-scan")
        argv.extend(["--deep-scan-tools", config.get("deep_scan_tools", "codeql,sonarqube")])

    result = run_parallel_main(argv)
    if result != 0:
        print(f"{Colors.RED}Batch analysis finished with errors.{Colors.ENDC}")
        return

    # Prompt to open dashboard
    open_dash = input(f"\n{Colors.BOLD}Open dashboard to view results? (Y/n): {Colors.ENDC}").strip().lower()
    if open_dash != "n":
        _open_dashboard(config)


def _run_deep_scan(config: dict) -> None:
    """Run CodeQL/SonarQube deep scan on AI commits from input JSON."""
    try:
        from src.metrics.deep_scan import (
            run_deep_scan, get_deep_scan_status, print_deep_scan_status,
            is_codeql_available, is_sonarqube_available
        )
    except ImportError:
        print(f"{Colors.RED}Deep scan module not available.{Colors.ENDC}")
        return

    # Check tool availability
    status = get_deep_scan_status()
    if not status.get("codeql") and not status.get("sonarqube"):
        print(f"\n{Colors.YELLOW}⚠ No deep scan tools available!{Colors.ENDC}")
        print_deep_scan_status()
        return

    # Ask for input JSON (same as regular analysis)
    print(f"\n{Colors.BOLD}🔬 Deep Scan AI Commits{Colors.ENDC}")
    print(f"{'-' * 50}")
    print(f"  Deep scan analyzes AI commits from your input JSON file")
    print(f"  using CodeQL/SonarQube for more accurate issue detection.")
    print(f"{'-' * 50}")

    default_input = config.get("last_input") or ""
    input_path = _prompt("Path to commits JSON file", default_input)

    if not input_path:
        print(f"{Colors.YELLOW}No input file specified.{Colors.ENDC}")
        return

    input_file = Path(input_path).expanduser().resolve()
    if not input_file.exists():
        print(f"{Colors.RED}File not found: {input_path}{Colors.ENDC}")
        return

    # Load commits from JSON
    try:
        data = json.loads(input_file.read_text())
        if isinstance(data, dict):
            commits = data.get("ai_commits", data.get("commits", []))
            repo_info = data.get("repo", "")
        else:
            commits = data
            repo_info = ""

        if not commits:
            print(f"{Colors.RED}No commits found in {input_path}{Colors.ENDC}")
            return

        print(f"\n{Colors.GREEN}Found {len(commits)} AI commits{Colors.ENDC}")
        if repo_info:
            print(f"  Repo: {Colors.BLUE}{repo_info}{Colors.ENDC}")

    except json.JSONDecodeError as e:
        print(f"{Colors.RED}Invalid JSON: {e}{Colors.ENDC}")
        return

    # Extract repo URL and clone/update
    first_commit = commits[0]
    repo_url = first_commit.get("repo_url", "")
    if not repo_url and repo_info:
        repo_url = f"https://github.com/{repo_info}"

    if not repo_url:
        print(f"{Colors.RED}Cannot determine repository URL from input file.{Colors.ENDC}")
        return

    # Clone/update repo
    from src.core.gitops import clone_or_update_repo
    repo_cache = Path(config["repo_cache"])

    print(f"\n{Colors.BLUE}Cloning/updating repository...{Colors.ENDC}")
    repo_dir = clone_or_update_repo(repo_url, repo_cache)

    if not repo_dir:
        print(f"{Colors.RED}Failed to clone repository: {repo_url}{Colors.ENDC}")
        return

    print(f"{Colors.GREEN}Repository ready: {repo_dir}{Colors.ENDC}")

    # Ask for commit limit
    limit = config.get("limit", 0)
    limit_input = _prompt("Commits to analyze (0 = all)", str(limit))
    try:
        limit = max(0, int(limit_input))
    except ValueError:
        limit = 0

    if limit > 0 and limit < len(commits):
        commits = commits[:limit]
        print(f"  Analyzing first {limit} commits")

    # Detect language
    print(f"\n{Colors.BOLD}🔍 Detecting language...{Colors.ENDC}")
    lang_counts = {}
    for ext, lang in [(".py", "python"), (".js", "javascript"), (".ts", "javascript"),
                      (".go", "go"), (".java", "java"), (".rs", "rust")]:
        count = len(list(repo_dir.rglob(f"*{ext}")))
        if count > 0:
            lang_counts[lang] = lang_counts.get(lang, 0) + count

    primary_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "python"
    print(f"  Primary language: {Colors.BLUE}{primary_lang}{Colors.ENDC}")

    # Select tools
    tools = []
    if status.get("codeql"):
        if _yes_no("Run CodeQL analysis?", default=True):
            tools.append("codeql")
    if status.get("sonarqube"):
        if _yes_no("Run SonarQube analysis?", default=True):
            tools.append("sonarqube")

    if not tools:
        print(f"{Colors.YELLOW}No tools selected.{Colors.ENDC}")
        return

    # Ask analysis mode
    print(f"\n{Colors.BOLD}Analysis Mode:{Colors.ENDC}")
    print(f"  {Colors.GREEN}1){Colors.ENDC} Before/After comparison (accurate but slow)")
    print(f"  {Colors.GREEN}2){Colors.ENDC} Current HEAD scan (fast, shows issues in AI files)")
    mode = input(f"{Colors.BOLD}Select [1-2, default=1]: {Colors.ENDC}").strip() or "1"

    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    if mode == "1":
        # PROPER BEFORE/AFTER COMPARISON
        from src.metrics.deep_scan import analyze_ai_commits_deep

        print(f"\n{Colors.BOLD}🔬 Deep Scanning {len(commits)} AI Commits (Before/After){Colors.ENDC}")
        print(f"  Tools: {', '.join(tools)}")
        print(f"  {Colors.YELLOW}⚠ This will checkout each commit - may take a while!{Colors.ENDC}\n")

        results = analyze_ai_commits_deep(repo_dir, commits, primary_lang, tools=tools)

        # Display results
        print(f"\n{Colors.BOLD}{'=' * 50}{Colors.ENDC}")
        print(f"{Colors.BOLD}DEEP SCAN RESULTS (Before/After Comparison){Colors.ENDC}")
        print(f"{Colors.BOLD}{'=' * 50}{Colors.ENDC}")
        print(f"Repo: {Colors.BLUE}{repo_info}{Colors.ENDC}")
        print(f"AI Commits analyzed: {Colors.GREEN}{results.get('commits_analyzed', 0)}{Colors.ENDC}")

        summary = results.get("summary", {})
        print(f"\n{Colors.HEADER}*** ISSUES INTRODUCED BY AI ***{Colors.ENDC}")
        print(f"  Total introduced: {Colors.RED}{summary.get('total_introduced', 0)}{Colors.ENDC}")
        print(f"  Total fixed: {Colors.GREEN}{summary.get('total_fixed', 0)}{Colors.ENDC}")
        print(f"  Net change: {summary.get('net_change', 0)}")

        if summary.get("by_severity"):
            print(f"\n  By Severity:")
            for sev, count in summary.get("by_severity", {}).items():
                print(f"    {sev}: {count}")

        if summary.get("by_type"):
            print(f"\n  By Type:")
            for itype, count in summary.get("by_type", {}).items():
                print(f"    {itype}: {count}")

        # Show commits with issues
        commits_with_issues = [c for c in results.get("commits", []) if c.get("issues_introduced_count", 0) > 0]
        if commits_with_issues:
            print(f"\n{Colors.HEADER}Commits that introduced issues:{Colors.ENDC}")
            for c in commits_with_issues[:10]:
                sha = c.get("commit", "")[:8]
                intro = c.get("issues_introduced_count", 0)
                fixed = c.get("issues_fixed_count", 0)
                print(f"  {sha}: +{intro} introduced, -{fixed} fixed")

        results["input_file"] = str(input_file)
        results["analysis_mode"] = "before_after"

    else:
        # FAST MODE: Current HEAD scan
        print(f"\n{Colors.BOLD}🔬 Deep Scanning Current HEAD{Colors.ENDC}")
        print(f"  Tools: {', '.join(tools)}")
        print(f"  This scans current state, filtered to AI-touched files.\n")

        baseline_results = run_deep_scan(repo_dir, primary_lang, tools=tools)

        # Track which files were touched by AI commits
        from src.core.gitops import list_changed_files_with_status
        ai_touched_files = set()
        for commit in commits:
            sha = commit.get("sha", commit.get("commit_hash", ""))
            if sha:
                try:
                    changes = list_changed_files_with_status(repo_dir, sha)
                    for file_path, status_char in changes:
                        if status_char in ('A', 'M'):
                            ai_touched_files.add(file_path)
                except Exception:
                    pass

        # Filter issues to AI-touched files
        all_issues = baseline_results.get("combined", {}).get("all_issues", [])
        ai_issues = [i for i in all_issues if i.get("file", "") in ai_touched_files]

        # Display results
        print(f"\n{Colors.BOLD}{'=' * 50}{Colors.ENDC}")
        print(f"{Colors.BOLD}DEEP SCAN RESULTS (Current HEAD){Colors.ENDC}")
        print(f"{Colors.BOLD}{'=' * 50}{Colors.ENDC}")
        print(f"Repo: {Colors.BLUE}{repo_info}{Colors.ENDC}")
        print(f"AI Commits: {Colors.GREEN}{len(commits)}{Colors.ENDC}")
        print(f"Files touched by AI: {Colors.GREEN}{len(ai_touched_files)}{Colors.ENDC}")

        print(f"\n{Colors.HEADER}Issues in AI-touched files:{Colors.ENDC}")
        print(f"  Total: {Colors.YELLOW}{len(ai_issues)}{Colors.ENDC}")

        combined = baseline_results.get('combined', {})
        print(f"\n{Colors.HEADER}Issues in entire repo:{Colors.ENDC}")
        print(f"  Total: {combined.get('total_issues', 0)}")
        print(f"  Security: {combined.get('security_issues', 0)}")
        print(f"  Quality: {combined.get('quality_issues', 0)}")

        results = {
            **baseline_results,
            "ai_commits_analyzed": len(commits),
            "ai_touched_files": list(ai_touched_files),
            "ai_issues": ai_issues,
            "ai_issues_count": len(ai_issues),
            "input_file": str(input_file),
            "analysis_mode": "current_head",
        }

    # Save results
    repo_folder = repo_info.replace("/", "_") if repo_info else f"{repo_dir.parent.name}_{repo_dir.name}"
    out_dir = Path(config["out_dir"]) / repo_folder
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "1":
        deep_scan_file = out_dir / "deep_scan_commits.json"
    else:
        deep_scan_file = out_dir / "deep_scan_results.json"

    deep_scan_file.write_text(json.dumps(results, indent=2))
    print(f"\n{Colors.GREEN}✓ Results saved to: {deep_scan_file}{Colors.ENDC}")


def _clear_output(config: dict) -> None:
    """Clear output files and debug folder."""
    import shutil

    out_dir = Path(config["out_dir"])

    if not out_dir.exists():
        print(f"{Colors.YELLOW}No output directory found.{Colors.ENDC}")
        return

    # Find repo subfolders and root files
    repo_dirs = [d for d in out_dir.iterdir() if d.is_dir()]
    root_files = list(out_dir.glob("*.json"))

    print(f"\n{Colors.BOLD}📁 Output contents in {out_dir}:{Colors.ENDC}")
    for f in root_files:
        print(f"  • {f.name}")
    for d in repo_dirs:
        file_count = len(list(d.glob("**/*.json")))
        print(f"  📂 {d.name}/ ({file_count} files)")

    if not root_files and not repo_dirs:
        print(f"{Colors.YELLOW}No output files to clear.{Colors.ENDC}")
        return

    print(f"\n{Colors.BOLD}What to clear?{Colors.ENDC}")
    print(f"  {Colors.GREEN}1){Colors.ENDC} All output (repos + files)")
    print(f"  {Colors.GREEN}2){Colors.ENDC} Select specific repo to clear")
    print(f"  {Colors.GREEN}3){Colors.ENDC} Checkpoint only")
    print(f"  {Colors.YELLOW}4){Colors.ENDC} Cancel")

    choice = input(f"{Colors.BOLD}Select [1-4]: {Colors.ENDC}").strip()

    if choice == "1":
        for f in root_files:
            f.unlink()
        for d in repo_dirs:
            shutil.rmtree(d)
        print(f"{Colors.GREEN}✓ All output files cleared.{Colors.ENDC}")
    elif choice == "2":
        if not repo_dirs:
            print(f"{Colors.YELLOW}No repo folders found.{Colors.ENDC}")
            return
        print(f"\n{Colors.BOLD}Select repo to clear:{Colors.ENDC}")
        for i, d in enumerate(repo_dirs, 1):
            print(f"  {Colors.GREEN}{i}){Colors.ENDC} {d.name}")
        repo_choice = input(f"{Colors.BOLD}Select [1-{len(repo_dirs)}]: {Colors.ENDC}").strip()
        try:
            idx = int(repo_choice) - 1
            if 0 <= idx < len(repo_dirs):
                shutil.rmtree(repo_dirs[idx])
                # Update repos.json
                repos_manifest = out_dir / "repos.json"
                if repos_manifest.exists():
                    repos = json.loads(repos_manifest.read_text())
                    repo_name = repo_dirs[idx].name
                    if repo_name in repos:
                        repos.remove(repo_name)
                        repos_manifest.write_text(json.dumps(repos, indent=2))
                print(f"{Colors.GREEN}✓ Cleared {repo_dirs[idx].name}{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}Invalid selection.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.YELLOW}Invalid selection.{Colors.ENDC}")
    elif choice == "3":
        checkpoint = Path(config["checkpoint"])
        if checkpoint.exists():
            checkpoint.unlink()
            print(f"{Colors.GREEN}✓ Checkpoint cleared.{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}No checkpoint found.{Colors.ENDC}")
    else:
        print(f"{Colors.YELLOW}Cancelled.{Colors.ENDC}")
