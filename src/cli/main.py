"""
CLI main entry point and interactive menu loop.
"""

import sys
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_pipeline import main as run_pipeline_main  # noqa: E402

from src.cli.colors import Colors  # noqa: E402
from src.cli.config import _load_config  # noqa: E402
from src.cli.menus import _quick_start, _settings_menu  # noqa: E402
from src.cli.dashboard import _show_summary, _open_dashboard  # noqa: E402
from src.cli.batch import _batch_analyze, _run_deep_scan, _clear_output  # noqa: E402


def _print_header():
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}  🔬 AI Code Quality Research Tool{Colors.ENDC}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.ENDC}")


def _print_menu():
    print(f"\n{Colors.BOLD}What would you like to do?{Colors.ENDC}")
    print(f"  {Colors.GREEN}1){Colors.ENDC} Analyze commits      - Run full analysis on AI commits")
    print(f"  {Colors.GREEN}2){Colors.ENDC} Batch analyze        - Process multiple repos at once")
    print(f"  {Colors.GREEN}3){Colors.ENDC} Deep scan            - CodeQL/SonarQube on AI commits")
    print(f"  {Colors.GREEN}4){Colors.ENDC} View results         - Show analysis summary")
    print(f"  {Colors.GREEN}5){Colors.ENDC} Open dashboard       - Visual results in browser")
    print(f"  {Colors.GREEN}6){Colors.ENDC} Settings             - Configure analysis options")
    print(f"  {Colors.GREEN}7){Colors.ENDC} Clear output         - Remove previous results")
    print(f"  {Colors.RED}0){Colors.ENDC} Exit")
    print(f"{Colors.BLUE}{'-' * 60}{Colors.ENDC}")


def main() -> int:
    # Handle command-line mode
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode in {"pipeline", "run", "analyze"}:
            return run_pipeline_main(sys.argv[2:])
        if mode == "dashboard":
            _open_dashboard(_load_config())
            return 0
        if mode == "summary":
            _show_summary(_load_config())
            return 0
        # Default: treat as pipeline args (--input, etc.)
        return run_pipeline_main(sys.argv[1:])

    # Interactive menu mode
    config = _load_config()

    try:
        while True:
            _print_header()
            _print_menu()
            choice = input(f"{Colors.BOLD}Select [0-7]: {Colors.ENDC}").strip()

            if choice in {"1", ""}:
                return _quick_start(config)
            if choice == "2":
                _batch_analyze(config)
                continue
            if choice == "3":
                _run_deep_scan(config)
                continue
            if choice == "4":
                _show_summary(config)
                continue
            if choice == "5":
                _open_dashboard(config)
                continue
            if choice == "6":
                _settings_menu(config)
                continue
            if choice == "7":
                _clear_output(config)
                continue
            if choice == "0":
                print(f"\n{Colors.GREEN}Goodbye!{Colors.ENDC}")
                return 0
            print(f"{Colors.RED}Invalid choice. Try again.{Colors.ENDC}")
    except KeyboardInterrupt:
        print(f"\n{Colors.GREEN}Goodbye! 👋{Colors.ENDC}")
        return 0
