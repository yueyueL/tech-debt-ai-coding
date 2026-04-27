"""
Blocked rules configuration for filtering false positive issues.

This module contains rules that should be filtered out from analysis
because they are commonly false positives in specific contexts.

Add new rules here as needed - they will be automatically applied
across all analyzers.
"""

import re
from typing import Set, Dict, List, Optional

# ============================================================================
# BLOCKED RULES (always filtered)
# ============================================================================
# Rules in this set will be filtered out from all analysis results.
# Each rule should have a comment explaining why it's blocked.

BLOCKED_RULES: Set[str] = {
    # Bandit rules intentionally kept: the paper treats them as insecure
    # patterns that can become vulnerabilities after later code changes or
    # broader system integration, so filter_issues must NOT drop them.
    # ---------------------------------------------------------------------
    # ESLint (JavaScript/TypeScript)
    # ---------------------------------------------------------------------
    "no-console",  # console statement - OK in CLI tools, scripts, debugging
    "curly",       # missing curly braces - style preference, not a bug

    # ---------------------------------------------------------------------
    # Pylint (Python)
    # ---------------------------------------------------------------------
    # These are frequently false positives in large-scale offline analysis
    # where we do NOT install each repo's dependencies and do not run a full
    # project-aware type checker. Counting them would destroy metric credibility.
    "import-error",        # E0401: module not found (often dependency not installed)
    "no-name-in-module",   # E0611: name not in module (often stub/dependency mismatch)
}

# ============================================================================
# CONTEXT-SENSITIVE RULES (filtered based on file path/content)
# ============================================================================

# Rules that are false positives in test files
# NOTE: Bandit hardcoded-password rules (B105/B106/B107) intentionally left in
# the counted set even for tests — the paper treats them as insecure patterns
# that can leak into production via copy/paste or fixture reuse.
TEST_FILE_FP_RULES: Set[str] = {
    # Hardcoded credentials in test files are mock data, not real secrets
    "node_api_key",
    "node_password",
    "hardcoded_password",
    "hardcoded_password_default",
    "hardcoded_password_funcarg",
    # JWT tokens in tests are fixtures
    "jwt_exposed",
    "hardcoded_jwt_secret",
}

# Rules that are false positives in simulation/mock code
SIMULATION_FP_RULES: Set[str] = {
    # Math.random() in simulations is intentional, not a crypto weakness
    "node_insecure_random_generator",
    "insecure_random",
}

# Rules that are false positives in developer tools/CLI scripts
# NOTE: Semantic verification in llm_judge.py handles context-aware decisions.
# This list is for FAST pre-filtering only (obvious false positives).
# Bandit B404/B108 intentionally removed — the paper counts them as insecure
# patterns that can become vulnerabilities under later changes or integration.
DEV_TOOLS_FP_RULES: Set[str] = set()

# Rules that are usually too style-heavy / context-sensitive to show by default.
# These are still stored in raw outputs; callers can use this set to mark them
# as low-signal without discarding them from the dataset.
LOW_SIGNAL_RULES: Set[str] = {
    # Pylint style/convention
    "line-too-long",
    "trailing-whitespace",
    "missing-function-docstring",
    "missing-module-docstring",
    "missing-class-docstring",
    "invalid-name",
    "bad-indentation",
    "consider-using-f-string",
    "too-many-arguments",
    "too-many-locals",
    "too-many-positional-arguments",
    "too-few-public-methods",
    "no-else-return",
    "logging-fstring-interpolation",
    "import-outside-toplevel",
    # ESLint style/convention
    "@typescript-eslint/no-magic-numbers",
    "no-magic-numbers",
    "sort-keys",
    "one-var",
    "id-length",
    "@typescript-eslint/explicit-member-accessibility",
    "@typescript-eslint/explicit-function-return-type",
    "@typescript-eslint/explicit-module-boundary-types",
    "@typescript-eslint/member-ordering",
    "@typescript-eslint/consistent-type-imports",
    "@typescript-eslint/no-explicit-any",
    "@typescript-eslint/no-inferrable-types",
    "@typescript-eslint/init-declarations",
    "@typescript-eslint/class-methods-use-this",
    "@typescript-eslint/method-signature-style",
    "@typescript-eslint/no-non-null-assertion",
    "@typescript-eslint/no-require-imports",
    "@typescript-eslint/prefer-readonly",
    "@typescript-eslint/naming-convention",
    "@typescript-eslint/sort-type-constituents",
    "@typescript-eslint/no-empty-object-type",
    "capitalized-comments",
    "camelcase",
    "class-methods-use-this",
    "consistent-return",
    "curly",
    "default-case",
    "func-names",
    "func-style",
    "guard-for-in",
    "init-declarations",
    "line-comment-position",
    "logical-assignment-operators",
    "max-lines",
    "max-lines-per-function",
    "max-statements",
    "multiline-comment-style",
    "no-bitwise",
    "no-console",
    "no-continue",
    "no-inline-comments",
    "no-negated-condition",
    "no-nested-ternary",
    "no-param-reassign",
    "no-plusplus",
    "no-ternary",
    "no-undefined",
    "no-underscore-dangle",
    "no-use-before-define",
    "@typescript-eslint/no-use-before-define",
    "no-var",
    "no-void",
    "object-shorthand",
    "prefer-arrow-callback",
    "prefer-const",
    "prefer-destructuring",
    "prefer-named-capture-group",
    "prefer-rest-params",
    "prefer-spread",
    "prefer-template",
    "require-await",
    "require-unicode-regexp",
    "sort-imports",
    "sort-vars",
    "strict",
    "vars-on-top",
    # Additional noise rules found in data analysis
    "no-invalid-this",                     # "Unexpected 'this'" - style rule, 28K issues
    "@typescript-eslint/array-type",       # "Use T[] instead of Array<T>" - style preference
    "@typescript-eslint/max-params",       # too many params (same as pylint too-many-arguments)
    "@typescript-eslint/consistent-type-definitions",  # interface vs type - style
    "@typescript-eslint/parameter-properties",  # constructor parameter properties - style
    "@typescript-eslint/prefer-for-of",    # for-of preference - style
    "@typescript-eslint/no-empty-function",  # empty function body - style
    "no-empty-function",                   # same for JS
    "@typescript-eslint/prefer-nullish-coalescing",  # ?? vs || - style
    "@typescript-eslint/no-unnecessary-condition",  # needs type info, often FP
}

# Common ambient types / framework globals that show up as no-undef noise when
# TypeScript files are linted without the full project runtime/type context.
TS_NO_UNDEF_AMBIENT_NAMES: Set[str] = {
    "$",
    "_",
    "$derived",
    "$state",
    "AbortSignal",
    "Bun",
    "Byond",
    "CloseEvent",
    "Deno",
    "DOMException",
    "Document",
    "Electron",
    "Hi",
    "Image",
    "Intl",
    "JSX",
    "MessageEvent",
    "MediaQueryList",
    "MediaQueryListEvent",
    "Meteor",
    "MouseEvent",
    "Node",
    "NodeJS",
    "ReadableStream",
    "React",
    "RequestInit",
    "SVGElement",
    "SVGSVGElement",
    "Template",
    "TouchEvent",
    "Window",
    "WebdriverIO",
    "YT",
    "alert",
    "assert",
    "chrome",
    "customElements",
    "define",
    "jQuery",
    "ko",
    "location",
    "postMessage",
    "self",
    "setImmediate",
}

TS_NO_UNDEF_AMBIENT_PREFIXES = (
    "Abort",
    "ArrayBuffer",
    "BigInt",
    "Blob",
    "Canvas",
    "CustomEvent",
    "DataView",
    "DOM",
    "Document",
    "Element",
    "Event",
    "File",
    "Float",
    "FormData",
    "HTML",
    "Headers",
    "Image",
    "Intersection",
    "Intl",
    "Keyboard",
    "Map",
    "MediaQuery",
    "Message",
    "Mutation",
    "Node",
    "Observer",
    "Promise",
    "Proxy",
    "React",
    "Readable",
    "Reflect",
    "Request",
    "Resize",
    "Response",
    "Set",
    "SVG",
    "Symbol",
    "Text",
    "Touch",
    "URL",
    "Uint",
    "Weak",
    "Window",
    "Writable",
)

# Keywords that indicate simulation/mock code (case-insensitive)
# NOTE: Files matching these should already be filtered by classify_path().
# This is a backup for edge cases.
SIMULATION_KEYWORDS: Set[str] = {
    "simulation", "simulator", "simulate",
    "mock", "mocked", "mocking",
    "stub", "stubbed",
    "fake", "faked",
    "quantum",  # Quantum computing simulations
}

# ============================================================================
# TEST FILE DETECTION
# ============================================================================

# Patterns that indicate test files (ALL LANGUAGES)
TEST_FILE_PATTERNS: List[re.Pattern] = [
    # Directory patterns (universal)
    re.compile(r"[/\\]tests?[/\\]", re.IGNORECASE),           # test/ or tests/
    re.compile(r"[/\\]__tests__[/\\]", re.IGNORECASE),        # __tests__/ (Jest)
    re.compile(r"[/\\]spec[/\\]", re.IGNORECASE),             # spec/ (RSpec, Jasmine)
    re.compile(r"[/\\]fixtures?[/\\]", re.IGNORECASE),        # fixture/ or fixtures/
    re.compile(r"[/\\]mocks?[/\\]", re.IGNORECASE),           # mock/ or mocks/
    re.compile(r"[/\\]testdata[/\\]", re.IGNORECASE),         # testdata/ (Go convention)
    re.compile(r"[/\\]testing[/\\]", re.IGNORECASE),          # testing/
    
    # Python test patterns
    re.compile(r"_test\.py$", re.IGNORECASE),                 # *_test.py
    re.compile(r"test_[^/\\]+\.py$", re.IGNORECASE),          # test_*.py
    re.compile(r"[/\\]conftest\.py$", re.IGNORECASE),         # conftest.py (pytest)
    
    # JavaScript/TypeScript test patterns
    re.compile(r"\.test\.[jt]sx?$", re.IGNORECASE),           # *.test.js, *.test.ts, etc.
    re.compile(r"\.spec\.[jt]sx?$", re.IGNORECASE),           # *.spec.js, *.spec.ts, etc.
    re.compile(r"[/\\]jest\.config\.[jt]s$", re.IGNORECASE),  # jest.config.js
    re.compile(r"[/\\]vitest\.config\.[jt]s$", re.IGNORECASE),# vitest.config.ts
    re.compile(r"[/\\]cypress[/\\]", re.IGNORECASE),          # cypress/ (E2E)
    re.compile(r"[/\\]playwright[/\\]", re.IGNORECASE),       # playwright/ (E2E)
    
    # Go test patterns
    re.compile(r"_test\.go$", re.IGNORECASE),                 # *_test.go
    
    # Java/Kotlin test patterns
    re.compile(r"Test\.java$"),                               # *Test.java
    re.compile(r"Tests\.java$"),                              # *Tests.java
    re.compile(r"Test\.kt$"),                                 # *Test.kt
    re.compile(r"[/\\]src[/\\]test[/\\]", re.IGNORECASE),     # src/test/ (Maven/Gradle)
    
    # Rust test patterns
    re.compile(r"[/\\]tests[/\\][^/\\]+\.rs$", re.IGNORECASE),# tests/*.rs
    
    # Ruby test patterns  
    re.compile(r"_spec\.rb$", re.IGNORECASE),                 # *_spec.rb (RSpec)
    re.compile(r"_test\.rb$", re.IGNORECASE),                 # *_test.rb (Minitest)
    
    # C#/.NET test patterns
    re.compile(r"Tests?\.cs$"),                               # *Test.cs, *Tests.cs
    re.compile(r"[/\\][^/\\]+\.Tests?[/\\]", re.IGNORECASE),  # *.Tests/ project
]

# Patterns that indicate developer tools / CLI scripts (ALL LANGUAGES)
# NOTE: Be SPECIFIC - avoid broad patterns like "utils/" that match production code
DEV_TOOL_PATTERNS: List[re.Pattern] = [
    # Python entry points
    re.compile(r"[/\\]cli\.py$", re.IGNORECASE),              # cli.py
    re.compile(r"[/\\]__main__\.py$", re.IGNORECASE),         # __main__.py
    
    # JavaScript/TypeScript entry points (CLI tools)
    re.compile(r"[/\\]cli\.[jt]s$", re.IGNORECASE),           # cli.js, cli.ts
    re.compile(r"[/\\]cli[/\\]index\.[jt]s$", re.IGNORECASE), # cli/index.js
    
    # Build/dev scripts (all languages)
    re.compile(r"[/\\]scripts?[/\\][^/\\]+\.(py|js|ts|sh|rb)$", re.IGNORECASE),
    re.compile(r"[/\\]bin[/\\][^/\\]+$", re.IGNORECASE),      # bin/command
    re.compile(r"[/\\]tools?[/\\][^/\\]+\.(py|js|ts|sh|go)$", re.IGNORECASE),
    
    # Dev servers (JS/TS)
    re.compile(r"dev[-_]?server\.[jt]sx?$", re.IGNORECASE),   # dev-server.js
    re.compile(r"[/\\]serve\.[jt]s$", re.IGNORECASE),         # serve.js, serve.ts
    
    # Go CLI tools
    re.compile(r"[/\\]cmd[/\\][^/\\]+[/\\]main\.go$", re.IGNORECASE),  # cmd/*/main.go
]


# ============================================================================
# RULE METADATA (optional, for documentation/UI)
# ============================================================================

RULE_METADATA: Dict[str, Dict] = {
    "B101": {
        "name": "Assert Detected",
        "tool": "bandit",
        "reason": "Using assert in test files is expected (pytest pattern)",
        "severity": "low",
    },
    "no-console": {
        "name": "Console Statement",
        "tool": "eslint",
        "reason": "Console output is intentional in CLI tools and scripts",
        "severity": "warning",
    },
    "curly": {
        "name": "Missing Curly Braces",
        "tool": "eslint",
        "reason": "Style preference, single-line statements are valid",
        "severity": "warning",
    },
    "node_api_key": {
        "name": "Hardcoded API Key",
        "tool": "semgrep/njsscan",
        "reason": "Often false positive in test files (mock credentials)",
        "severity": "error",
        "context_sensitive": True,
    },
    "node_insecure_random_generator": {
        "name": "Insecure Random Generator",
        "tool": "semgrep/njsscan",
        "reason": "Math.random() is acceptable for non-cryptographic uses (IDs, simulations)",
        "severity": "warning",
        "context_sensitive": True,
    },
}


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def is_test_file(file_path: str) -> bool:
    """
    Check if a file path indicates a test file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file appears to be a test file
    """
    if not file_path:
        return False
    
    for pattern in TEST_FILE_PATTERNS:
        if pattern.search(file_path):
            return True
    return False


def is_dev_tool(file_path: str) -> bool:
    """
    Check if a file path indicates a developer tool or CLI script.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file appears to be a dev tool
    """
    if not file_path:
        return False
        
    for pattern in DEV_TOOL_PATTERNS:
        if pattern.search(file_path):
            return True
    return False


def has_simulation_context(file_content: Optional[str], file_path: str = "") -> bool:
    """
    Check if file content or path indicates simulation/mock code.
    
    Args:
        file_content: Content of the file (optional)
        file_path: Path to the file
        
    Returns:
        True if the file appears to contain simulation/mock code
    """
    # Check file path for simulation keywords
    path_lower = file_path.lower()
    for keyword in SIMULATION_KEYWORDS:
        if keyword in path_lower:
            return True
    
    # Check file content if provided
    if file_content:
        content_lower = file_content.lower()
        # Look for simulation keywords in comments or variable names
        for keyword in SIMULATION_KEYWORDS:
            # Check for keyword as whole word (not part of another word)
            if re.search(rf'\b{keyword}\b', content_lower):
                return True
    
    return False


def is_blocked(rule: str) -> bool:
    """Check if a rule is in the blocked list."""
    return rule in BLOCKED_RULES


def _extract_no_undef_identifier(message: str) -> str:
    match = re.match(r"^'([^']+)' is not defined\.$", message or "")
    return match.group(1) if match else ""


def is_likely_typescript_no_undef_false_positive(issue: dict, file_path: str = "") -> bool:
    """
    Detect common no-undef findings that are artifacts of isolated JS/TS analysis.
    """
    rule = issue.get("rule") or issue.get("symbol") or issue.get("rule_id") or ""
    normalized_path = (file_path or issue.get("file_path") or "").replace("\\", "/")
    lowered = normalized_path.lower()
    if rule != "no-undef" or not lowered.endswith((".js", ".jsx", ".ts", ".tsx", ".d.ts")):
        return False
    if lowered.endswith(".d.ts"):
        return True

    name = _extract_no_undef_identifier(str(issue.get("message") or ""))
    if not name:
        return False
    if name in TS_NO_UNDEF_AMBIENT_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in TS_NO_UNDEF_AMBIENT_PREFIXES)


def is_issue_low_signal(issue: dict, file_path: str = "") -> bool:
    """
    Return True for issues that should be hidden by default as low-signal noise.
    """
    rule = issue.get("rule") or issue.get("symbol") or issue.get("rule_id") or ""
    if rule in LOW_SIGNAL_RULES:
        return True

    message = str(issue.get("message") or "")
    if rule == "no-redeclare" and "built-in global variable" in message:
        return True
    if rule == "@typescript-eslint/no-unused-vars" and "only used as a type" in message:
        return True
    if is_likely_typescript_no_undef_false_positive(issue, file_path=file_path):
        return True
    return False


def get_issue_filter_context(
    file_path: str = "",
    file_content: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Compute reusable filtering context for a file.

    This lets analysis persist raw issues while downstream consumers
    re-apply the same blocked/context-sensitive filtering later without
    needing full file contents.
    """
    return {
        "is_test": is_test_file(file_path),
        "is_simulation": has_simulation_context(file_content, file_path),
        "is_dev": is_dev_tool(file_path),
    }


def filter_issues(
    issues: list, 
    rule_key: str = "rule",
    file_path: str = "",
    file_content: Optional[str] = None,
    context: Optional[Dict[str, bool]] = None,
) -> list:
    """
    Filter out blocked and false positive issues from a list.
    
    This function applies multiple filtering strategies:
    1. Always blocked rules (style issues, assert in tests, etc.)
    2. Context-sensitive rules (hardcoded secrets in test files, etc.)
    3. Simulation-aware rules (Math.random in quantum simulations, etc.)
    
    Args:
        issues: List of issue dictionaries
        rule_key: Key name for the rule field (default: "rule", could be "symbol")
        file_path: Path to the file being analyzed (for context detection)
        file_content: Content of the file (for deeper context analysis)
        
    Returns:
        Filtered list with false positives removed
    """
    # Determine context once for all issues
    filter_context = context or get_issue_filter_context(
        file_path=file_path,
        file_content=file_content,
    )
    is_test = filter_context.get("is_test", False)
    is_simulation = filter_context.get("is_simulation", False)
    is_dev = filter_context.get("is_dev", False)
    
    filtered = []
    for issue in issues:
        rule = issue.get(rule_key) or issue.get("symbol", "")
        
        # 1. Always blocked rules
        if rule in BLOCKED_RULES:
            continue
            
        # 2. Test file false positives (hardcoded credentials, etc.)
        if is_test and rule in TEST_FILE_FP_RULES:
            continue
            
        # 3. Simulation false positives (insecure random, etc.)
        if is_simulation and rule in SIMULATION_FP_RULES:
            continue

        # 4. Dev tool false positives (subprocess, etc.)
        if is_dev and rule in DEV_TOOLS_FP_RULES:
            continue
        
        filtered.append(issue)
    
    return filtered


def get_blocked_rules_description() -> str:
    """Get a human-readable description of blocked rules."""
    lines = ["Blocked Rules:"]
    
    lines.append("\n  Always Blocked:")
    for rule in sorted(BLOCKED_RULES):
        meta = RULE_METADATA.get(rule, {})
        reason = meta.get("reason", "No reason specified")
        lines.append(f"    - {rule}: {reason}")
    
    lines.append("\n  Test File False Positives:")
    for rule in sorted(TEST_FILE_FP_RULES):
        meta = RULE_METADATA.get(rule, {})
        reason = meta.get("reason", "Mock/fixture data in tests")
        lines.append(f"    - {rule}: {reason}")
    
    lines.append("\n  Simulation Code False Positives:")
    for rule in sorted(SIMULATION_FP_RULES):
        meta = RULE_METADATA.get(rule, {})
        reason = meta.get("reason", "Non-cryptographic usage")
        lines.append(f"    - {rule}: {reason}")
    
    return "\n".join(lines)
