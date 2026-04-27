#!/usr/bin/env python3
"""
Run a small reproducible Semgrep smoke test against checked-in fixtures.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples" / "semgrep"
PINNED_CONFIGS = ["p/default", "p/security-audit"]

EXAMPLES = [
    {
        "path": EXAMPLES_DIR / "python_requests_verify_false.py",
        "expected_pinned_min": 1,
        "label": "Python requests verify=False",
    },
    {
        "path": EXAMPLES_DIR / "python_yaml_unsafe_load.py",
        "expected_pinned_min": 1,
        "label": "Python unsafe yaml.load",
    },
    {
        "path": EXAMPLES_DIR / "javascript_eval.js",
        "expected_pinned_min": 1,
        "label": "JavaScript eval()",
    },
    {
        "path": EXAMPLES_DIR / "python_subprocess_shell_true.py",
        "expected_pinned_min": 1,
        "label": "Python subprocess shell=True (variable command)",
    },
    {
        "path": EXAMPLES_DIR / "python_subprocess_shell_true_literal.py",
        "expected_pinned_min": 0,
        "label": "Python subprocess shell=True (literal command)",
        "custom_rule": EXAMPLES_DIR / "custom_python_shell_true.yml",
        "expected_custom_min": 1,
    },
]


def run_semgrep(target: Path, configs: list[str]) -> dict:
    command = ["semgrep", "--json", "--quiet", "--disable-version-check"]
    for config in configs:
        command.extend(["--config", config])
    command.append(str(target))

    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    stdout = result.stdout.strip()
    if not stdout:
        return {"returncode": result.returncode, "results": [], "stderr": result.stderr.strip()}

    payload = json.loads(stdout)
    return {
        "returncode": result.returncode,
        "results": payload.get("results", []),
        "stderr": result.stderr.strip(),
    }


def summarize_results(results: list[dict]) -> str:
    if not results:
        return "0 findings"
    checks = ", ".join(result.get("check_id", "unknown") for result in results[:3])
    if len(results) > 3:
        checks += ", ..."
    return f"{len(results)} findings ({checks})"


def main() -> int:
    failures = []

    print("Pinned Semgrep configs:", ", ".join(PINNED_CONFIGS))
    print()

    for example in EXAMPLES:
        path = example["path"]
        pinned = run_semgrep(path, PINNED_CONFIGS)
        pinned_count = len(pinned["results"])

        print(f"[Pinned] {example['label']}: {summarize_results(pinned['results'])}")

        expected_pinned_min = example["expected_pinned_min"]
        if pinned_count < expected_pinned_min:
            failures.append(
                f"{path.name}: expected at least {expected_pinned_min} finding(s) with pinned configs, got {pinned_count}"
            )

        custom_rule = example.get("custom_rule")
        if custom_rule:
            custom = run_semgrep(path, [str(custom_rule)])
            custom_count = len(custom["results"])
            print(f"[Custom] {example['label']}: {summarize_results(custom['results'])}")
            expected_custom_min = example["expected_custom_min"]
            if custom_count < expected_custom_min:
                failures.append(
                    f"{path.name}: expected at least {expected_custom_min} finding(s) with custom rule, got {custom_count}"
                )

        print()

    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("All Semgrep smoke-test expectations matched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
