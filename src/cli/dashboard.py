"""
CLI result viewing: summary display and dashboard server.
"""

import json
from urllib.parse import parse_qs, urlencode, urlparse
from pathlib import Path

from src.cli.colors import Colors
from src.reporting.aggregate import is_tainted_commit


def _show_summary(config: dict) -> None:
    """Display a summary of the analysis results."""
    base_out_dir = Path(config["out_dir"])

    # Find repo subfolders or use base if flat structure
    repo_dirs = [d for d in base_out_dir.iterdir() if d.is_dir() and (d / "debt_metrics.json").exists()]

    # Fallback: check for flat structure (legacy)
    if not repo_dirs and (base_out_dir / "debt_metrics.json").exists():
        repo_dirs = [base_out_dir]

    if not repo_dirs:
        print(f"{Colors.YELLOW}No results found. Run analysis first.{Colors.ENDC}")
        return

    # If multiple repos, let user select
    if len(repo_dirs) > 1:
        print(f"\n{Colors.BOLD}📂 Available Results:{Colors.ENDC}")
        for i, d in enumerate(repo_dirs, 1):
            print(f"  {Colors.GREEN}{i}){Colors.ENDC} {d.name}")
        print(f"  {Colors.YELLOW}0){Colors.ENDC} All repos (combined summary)")
        choice = input(f"{Colors.BOLD}Select repo [1-{len(repo_dirs)}]: {Colors.ENDC}").strip()

        if choice == "0":
            # Show combined summary
            _show_combined_summary(repo_dirs, config)
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(repo_dirs):
                out_dir = repo_dirs[idx]
            else:
                out_dir = repo_dirs[0]
        except ValueError:
            out_dir = repo_dirs[0]
    else:
        out_dir = repo_dirs[0]

    debt_file = out_dir / "debt_metrics.json"
    destiny_file = out_dir / "destiny_metrics.json"

    try:
        debt = json.loads(debt_file.read_text())
        destiny = json.loads(destiny_file.read_text()) if destiny_file.exists() else []
    except json.JSONDecodeError:
        print(f"{Colors.RED}Error reading results.{Colors.ENDC}")
        return

    # Exclude tainted commits (shallow-clone parent-resolution fallback)
    debt = [c for c in debt if not is_tainted_commit(c)]

    # Calculate totals
    total_commits = len(debt)
    total_introduced = sum(c.get("summary", {}).get("total_issues_introduced", 0) for c in debt)
    total_fixed = sum(c.get("summary", {}).get("total_issues_fixed", 0) for c in debt)
    net = total_introduced - total_fixed

    avg_survival = 0
    if destiny:
        avg_survival = sum(d.get("survival_rate", 0) for d in destiny) / len(destiny) * 100

    print(f"\n{Colors.BOLD}📊 Analysis Summary: {out_dir.name}{Colors.ENDC}")
    print(f"{'-' * 40}")
    print(f"  Total commits analyzed: {Colors.BLUE}{total_commits}{Colors.ENDC}")
    print(f"  Issues introduced:      {Colors.RED}+{total_introduced}{Colors.ENDC}")
    print(f"  Issues fixed:           {Colors.GREEN}-{total_fixed}{Colors.ENDC}")
    net_color = Colors.RED if net > 0 else Colors.GREEN
    print(f"  Net debt change:        {net_color}{'+' if net > 0 else ''}{net}{Colors.ENDC}")
    print(f"  Avg survival rate:      {Colors.BLUE}{avg_survival:.1f}%{Colors.ENDC}")
    print(f"{'-' * 40}")
    print(f"\n  Results in: {Colors.BLUE}{out_dir}{Colors.ENDC}")
    details_dir = out_dir / "debug"
    if details_dir.exists():
        print(f"  Per-commit details: {Colors.BLUE}{details_dir}{Colors.ENDC}")
    else:
        print(f"  Per-commit details: {Colors.YELLOW}(disabled){Colors.ENDC}")
    input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.ENDC}")


def _show_combined_summary(repo_dirs: list, config: dict) -> None:
    """Show combined summary across all repos."""
    total_commits = 0
    total_introduced = 0
    total_fixed = 0
    total_survival = 0
    survival_count = 0

    for out_dir in repo_dirs:
        debt_file = out_dir / "debt_metrics.json"
        destiny_file = out_dir / "destiny_metrics.json"

        try:
            debt = [c for c in json.loads(debt_file.read_text()) if not is_tainted_commit(c)]
            total_commits += len(debt)
            total_introduced += sum(c.get("summary", {}).get("total_issues_introduced", 0) for c in debt)
            total_fixed += sum(c.get("summary", {}).get("total_issues_fixed", 0) for c in debt)

            if destiny_file.exists():
                destiny = json.loads(destiny_file.read_text())
                for d in destiny:
                    total_survival += d.get("survival_rate", 0)
                    survival_count += 1
        except (json.JSONDecodeError, FileNotFoundError):
            continue

    net = total_introduced - total_fixed
    avg_survival = (total_survival / survival_count * 100) if survival_count else 0

    print(f"\n{Colors.BOLD}📊 Combined Summary ({len(repo_dirs)} repos){Colors.ENDC}")
    print(f"{'-' * 40}")
    print(f"  Repos analyzed:         {Colors.BLUE}{len(repo_dirs)}{Colors.ENDC}")
    print(f"  Total commits:          {Colors.BLUE}{total_commits}{Colors.ENDC}")
    print(f"  Issues introduced:      {Colors.RED}+{total_introduced}{Colors.ENDC}")
    print(f"  Issues fixed:           {Colors.GREEN}-{total_fixed}{Colors.ENDC}")
    net_color = Colors.RED if net > 0 else Colors.GREEN
    print(f"  Net debt change:        {net_color}{'+' if net > 0 else ''}{net}{Colors.ENDC}")
    print(f"  Avg survival rate:      {Colors.BLUE}{avg_survival:.1f}%{Colors.ENDC}")
    print(f"{'-' * 40}")
    input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.ENDC}")


def _open_dashboard(config: dict) -> None:
    """Start a local server and open the dashboard."""
    import errno
    import functools
    import threading
    import webbrowser
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    root_dir = Path(__file__).resolve().parents[2]
    ui_dir = root_dir / "src" / "ui"

    if not ui_dir.exists():
        print(f"{Colors.RED}Dashboard not found at {ui_dir}{Colors.ENDC}")
        return

    # Auto-generate aggregate summary for the overview page
    out_dir = Path(config.get("out_dir", "out"))
    if out_dir.exists():
        try:
            from src.reporting import aggregate_and_save
            print(f"{Colors.BLUE}Updating aggregate summary...{Colors.ENDC}", end=" ", flush=True)
            _, recomputed = aggregate_and_save(str(out_dir))
            if recomputed:
                print(f"{Colors.GREEN}Done (refreshed).{Colors.ENDC}")
            else:
                print(f"{Colors.GREEN}Up-to-date.{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.YELLOW}Skipped ({e}).{Colors.ENDC}")

    print(f"\n{Colors.BLUE}Starting local server...{Colors.ENDC}")

    host = "127.0.0.1"
    preferred_ports = [8080, 8000, 8081]

    class _QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _write_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/__refresh_aggregate__":
                dataset = parse_qs(parsed.query).get("dataset", [out_dir.name])[0]
                if not dataset or not all(ch.isalnum() or ch in "._-" for ch in dataset):
                    self._write_json(400, {"ok": False, "error": "invalid dataset"})
                    return

                # Reproduction-package convention: data lives under results/<dataset>/;
                # legacy top-level <dataset>/ also accepted for back-compat.
                if dataset == out_dir.name:
                    dataset_dir = out_dir
                else:
                    candidate = root_dir / "results" / dataset
                    dataset_dir = candidate if candidate.is_dir() else root_dir / dataset
                if not dataset_dir.exists() or not dataset_dir.is_dir():
                    self._write_json(404, {"ok": False, "error": f"dataset not found: {dataset}"})
                    return

                try:
                    from src.reporting import aggregate_and_save

                    agg_path, recomputed = aggregate_and_save(str(dataset_dir))
                    agg_file = Path(agg_path)
                    self._write_json(200, {
                        "ok": True,
                        "dataset": dataset,
                        "recomputed": recomputed,
                        "aggregate_path": str(agg_file.relative_to(root_dir)),
                        "aggregate_mtime": agg_file.stat().st_mtime if agg_file.exists() else 0,
                    })
                except Exception as e:
                    self._write_json(500, {"ok": False, "error": str(e), "dataset": dataset})
                return

            super().do_GET()

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

    httpd = None
    for port in preferred_ports + [0]:
        try:
            handler = functools.partial(_QuietHandler, directory=str(root_dir))
            httpd = ThreadingHTTPServer((host, port), handler)
            break
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                continue
            raise

    if httpd is None:
        print(f"{Colors.RED}Failed to start server: could not bind to a port{Colors.ENDC}")
        return

    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    dataset_suffix = ""
    if out_dir.name != "out":
        dataset_suffix = f"?{urlencode({'dataset': out_dir.name})}"
    overview_url = f"http://{host}:{port}/src/ui/overview.html{dataset_suffix}"
    repo_url = f"http://{host}:{port}/src/ui/dashboard.html{dataset_suffix}"
    print(f"{Colors.GREEN}Overview:  {overview_url}{Colors.ENDC}")
    print(f"{Colors.GREEN}Per-repo:  {repo_url}{Colors.ENDC}")
    webbrowser.open(overview_url)

    print(f"\n{Colors.YELLOW}Server running. Press Ctrl+C or Enter to stop.{Colors.ENDC}")
    print(f"{Colors.YELLOW}If you are on a remote machine, use port forwarding to {port}.{Colors.ENDC}")
    try:
        input()
    except KeyboardInterrupt:
        pass

    httpd.shutdown()
    httpd.server_close()
    t.join(timeout=1.0)
    print(f"{Colors.GREEN}Server stopped.{Colors.ENDC}")
