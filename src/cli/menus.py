"""
CLI interactive menus: quick start and settings.
"""

from src.cli.colors import Colors
from src.cli.config import _prompt, _save_config, _run_pipeline, _yes_no
from src.cli.dashboard import _open_dashboard


def _quick_start(config: dict) -> int:
    default_input = config.get("last_input") or ""
    input_path = ""
    while not input_path:
        input_path = _prompt("Path to ai_commits.jsonl or ai_commit_summary.json", default_input)
    config["last_input"] = input_path
    _save_config(config)
    result = _run_pipeline(input_path, config)

    # After pipeline, ask to open dashboard
    if result == 0:
        print(f"\n{Colors.GREEN}✓ Analysis complete!{Colors.ENDC}")
        if _yes_no("Open dashboard to view results?", default=True):
            _open_dashboard(config)
    return result


def _settings_menu(config: dict) -> None:
    """Interactive settings menu with choices."""
    # Import deep scan status check
    try:
        from src.metrics.deep_scan import get_deep_scan_status
        deep_status = get_deep_scan_status()
    except ImportError:
        deep_status = {"codeql": False, "sonarqube": False, "docker": False}

    while True:
        print(f"\n{Colors.BOLD}⚙️  Settings{Colors.ENDC}")
        print(f"{'-' * 60}")

        # Key settings
        limit = config.get("limit", 0)
        limit_str = f"{Colors.BLUE}{limit} commits{Colors.ENDC}" if limit > 0 else f"{Colors.GREEN}all{Colors.ENDC}"
        workers = config.get("workers", 4)
        parallel = config.get("parallel", 4)

        # Deep scan status
        deep_scan_enabled = config.get("deep_scan", False)
        deep_scan_str = f"{Colors.GREEN}ON{Colors.ENDC}" if deep_scan_enabled else f"{Colors.RED}OFF{Colors.ENDC}"
        deep_tools = config.get("deep_scan_tools", "codeql,sonarqube")

        # Tool availability
        codeql_avail = f"{Colors.GREEN}✓{Colors.ENDC}" if deep_status.get("codeql") else f"{Colors.RED}✗{Colors.ENDC}"
        sonar_avail = f"{Colors.GREEN}✓{Colors.ENDC}" if deep_status.get("sonarqube") else f"{Colors.RED}✗{Colors.ENDC}"

        print(f"  {Colors.GREEN}1){Colors.ENDC} Commit limit:      {limit_str}")
        print(f"  {Colors.GREEN}2){Colors.ENDC} File workers:      {Colors.BLUE}{workers}{Colors.ENDC}")
        print(f"  {Colors.GREEN}3){Colors.ENDC} Repo workers:      {Colors.BLUE}{parallel}{Colors.ENDC}")
        print(f"  {Colors.GREEN}4){Colors.ENDC} Output directory:  {Colors.BLUE}{config['out_dir']}{Colors.ENDC}")
        print(f"  {Colors.GREEN}5){Colors.ENDC} Repo cache:        {Colors.BLUE}{config['repo_cache']}{Colors.ENDC}")
        print(f"  {Colors.GREEN}6){Colors.ENDC} Log level:         {Colors.BLUE}{config['log_level']}{Colors.ENDC}")
        print(f"{'-' * 60}")
        print(f"  {Colors.HEADER}Deep Scan (Tier-2):{Colors.ENDC}")
        print(f"  {Colors.GREEN}7){Colors.ENDC} Enable deep scan: {deep_scan_str}")
        print(f"  {Colors.GREEN}8){Colors.ENDC} Deep scan tools:  {Colors.BLUE}{deep_tools}{Colors.ENDC}")
        print(f"      CodeQL: {codeql_avail}  SonarQube: {sonar_avail}")
        print(f"{'-' * 60}")
        print(f"  {Colors.YELLOW}0){Colors.ENDC} Back to main menu")
        print(f"{'-' * 60}")

        choice = input(f"{Colors.BOLD}Select [0-8]: {Colors.ENDC}").strip()

        if choice == "1":
            print(f"\n  {Colors.BLUE}Limit: number of commits to analyze (0 = all){Colors.ENDC}")
            new_val = _prompt("Commit limit", str(config.get("limit", 0)))
            try:
                limit = max(0, int(new_val))
                config["limit"] = limit
                if limit > 0:
                    print(f"  {Colors.GREEN}✓ Limit set to {limit} commits{Colors.ENDC}")
                else:
                    print(f"  {Colors.GREEN}✓ Analyzing all commits{Colors.ENDC}")
            except ValueError:
                print(f"  {Colors.RED}Invalid number{Colors.ENDC}")
        elif choice == "2":
            print(f"\n  {Colors.BLUE}File workers: 1-16 (higher = faster per repo){Colors.ENDC}")
            new_val = _prompt("File workers", str(config.get("workers", 4)))
            try:
                workers = max(1, min(16, int(new_val)))
                config["workers"] = workers
                print(f"  {Colors.GREEN}✓ Workers set to {workers}{Colors.ENDC}")
            except ValueError:
                print(f"  {Colors.RED}Invalid number{Colors.ENDC}")
        elif choice == "3":
            print(f"\n  {Colors.BLUE}Repo workers: 1-64 (parallel repos in batch){Colors.ENDC}")
            new_val = _prompt("Repo workers", str(config.get("parallel", 4)))
            try:
                parallel = max(1, min(64, int(new_val)))
                config["parallel"] = parallel
                print(f"  {Colors.GREEN}✓ Repo workers set to {parallel}{Colors.ENDC}")
            except ValueError:
                print(f"  {Colors.RED}Invalid number{Colors.ENDC}")
        elif choice == "4":
            new_val = _prompt("Output directory", config["out_dir"])
            config["out_dir"] = new_val
            print(f"  {Colors.GREEN}✓ Output directory updated{Colors.ENDC}")
        elif choice == "5":
            new_val = _prompt("Repo cache directory", config["repo_cache"])
            config["repo_cache"] = new_val
            print(f"  {Colors.GREEN}✓ Repo cache updated{Colors.ENDC}")
        elif choice == "6":
            print(f"\n  {Colors.BLUE}Log levels: DEBUG, INFO, WARNING, ERROR{Colors.ENDC}")
            new_val = _prompt("Log level", config["log_level"])
            config["log_level"] = new_val.upper()
            print(f"  {Colors.GREEN}✓ Log level set to {config['log_level']}{Colors.ENDC}")
        elif choice == "7":
            # Toggle deep scan
            config["deep_scan"] = not config.get("deep_scan", False)
            status = "enabled" if config["deep_scan"] else "disabled"
            print(f"  {Colors.GREEN}✓ Deep scan {status}{Colors.ENDC}")
            if config["deep_scan"]:
                # Check tool availability
                if not deep_status.get("codeql") and not deep_status.get("sonarqube"):
                    print(f"  {Colors.YELLOW}⚠ No deep scan tools available!{Colors.ENDC}")
                    print(f"    Install CodeQL: brew install --cask codeql")
                    print(f"    Start SonarQube: docker run -d -p 9000:9000 sonarqube:lts-community")
        elif choice == "8":
            print(f"\n  {Colors.BLUE}Available tools: codeql, sonarqube{Colors.ENDC}")
            print(f"  {Colors.BLUE}Enter comma-separated list (e.g., 'codeql,sonarqube'){Colors.ENDC}")
            new_val = _prompt("Deep scan tools", config.get("deep_scan_tools", "codeql,sonarqube"))
            config["deep_scan_tools"] = new_val.lower().replace(" ", "")
            print(f"  {Colors.GREEN}✓ Deep scan tools set to: {config['deep_scan_tools']}{Colors.ENDC}")
        elif choice == "0":
            _save_config(config)
            print(f"{Colors.GREEN}✓ Settings saved{Colors.ENDC}")
            return
        else:
            print(f"{Colors.RED}Invalid choice{Colors.ENDC}")
