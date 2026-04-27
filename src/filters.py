import re
from pathlib import Path


NOISE_DIRS = {
    # Dependency directories
    "node_modules",
    "vendor",
    "bower_components",
    # Build output directories
    "dist",
    "build",
    "out",
    ".next",        # Next.js build output
    ".nuxt",        # Nuxt.js build output
    ".output",      # Nitro/Nuxt output
    ".svelte-kit",  # SvelteKit build output
    ".vercel",      # Vercel deployment
    ".netlify",     # Netlify deployment
    # Python artifacts
    "__pycache__",
    ".pytest_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    ".venv",
    "venv",
    "env",
    "site-packages",
    "test_env",
    "test-env",
    # Test/coverage output
    "coverage",
    ".nyc_output",
    "htmlcov",
    # IDE/editor directories
    ".idea",
    ".vscode",
    # Third party code
    "third_party",
    "third-party",
    "external",
    # Cache directories
    ".cache",
    ".turbo",
    ".parcel-cache",
    # Git internals
    ".git",
    # Static asset / bundled library directories
    # ASP.NET/MVC convention (bundled vendor scripts)
    "wwwroot",
    "Scripts",          # Common vendor scripts folder (ASP.NET, Django, etc.)
    # Well-known bundled/third-party JS libraries
    "monaco",           # Monaco Editor (VS Code editor component)
    "codemirror",       # CodeMirror editor
    "ckeditor",         # CKEditor rich text editor
    "tinymce",          # TinyMCE rich text editor
    # Java/C# build output
    "target",           # Maven/Gradle build output
    "bin",              # .NET build output
    "obj",              # .NET intermediate output
    # Static site generators
    "_site",            # Jekyll
    "public",           # Hugo/Gatsby (when it's a build output)
    # Bundled/compiled output
    "bundles",
    "packed",
    "compiled",
    # Django/Python web framework
    "staticfiles",      # Django collected static files
    "media",            # User uploads
    "migrations",       # Django auto-generated migrations
    # Rails
    "tmp",              # Rails temp/cache
    "log",              # Log directories
    # ASP.NET additional
    "App_Data",
    "App_Code",
    "App_GlobalResources",
    # Monorepo build artifacts
    "artifacts",
    ".angular",         # Angular CLI cache
}

DOC_DIRS = {"docs", "doc", "documentation", "wiki"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "e2e", "integration", "unit"}
DATA_DIRS = {"data", "datasets", "dataset", "fixtures", "testdata", "test_data"}
EXAMPLE_DIRS = {"example", "examples", "demo", "demos", "sample", "samples", "tutorial", "tutorials"}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rb",
    ".rs",
    ".cpp",
    ".cc",
    ".c",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".swift",
    ".kt",
    ".kts",
    ".scala",
    ".m",
    ".mm",
    ".lua",
    ".sh",
    ".bat",
    ".ps1",
}

DOC_EXTENSIONS = {
    ".md",
    ".rst",
    ".txt",
    ".adoc",
    ".org",
    ".markdown",
}

CONFIG_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
    ".env",
}

DATA_EXTENSIONS = {".csv", ".tsv", ".parquet", ".jsonl"}


# Regex: webpack/rollup/parcel chunk files (numeric prefix like 105.foo.js, 292.bar.js)
_WEBPACK_CHUNK_RE = re.compile(r"^\d+\.\w+.*\.js$")

# Known bundled library filenames (case-insensitive stems)
_KNOWN_VENDOR_STEMS = {
    "jquery", "jquery-ui", "jquery.validate", "jquery.unobtrusive",
    "bootstrap", "popper", "react", "react-dom", "angular", "vue",
    "lodash", "underscore", "moment", "dayjs", "axios",
    "d3", "chart", "three", "pixi",
    "graphiql", "codemirror", "ace", "monaco",
    "highlight", "prism", "marked", "showdown",
    "socket.io", "signalr",
}


def is_noise_path(path: str) -> bool:
    """
    Check if a path is noise (build artifacts, dependencies, cache,
    bundled/vendor libraries, etc.) that should not be analyzed for
    code quality.
    
    This is critical for research accuracy: analyzing minified vendor
    code (e.g., monaco editor, graphiql bundles) would introduce
    massive false positives.
    """
    normalized = path.strip().lstrip("/")
    parts = normalized.split("/")
    
    # Check each path component against noise directories
    for part in parts:
        # Exact match
        if part in NOISE_DIRS:
            return True
        # Pattern match for .egg-info etc
        if part.endswith(".egg-info"):
            return True
    
    # Get filename
    filename = parts[-1] if parts else normalized
    filename_lower = filename.lower()
    
    # Skip minified files (.min.js, .min.css, .bundle.js, .chunk.js)
    if filename_lower.endswith((".min.js", ".min.css", ".bundle.js", ".chunk.js")):
        return True
    
    # Skip webpack/rollup/parcel chunk files (e.g., 105.graphiql-orchard.js, 292.foo.js)
    if _WEBPACK_CHUNK_RE.match(filename):
        return True
    
    # Skip compiled/generated files
    if filename_lower.endswith((".pyc", ".pyo", ".class", ".o", ".so", ".dll")):
        return True
    
    # Skip map files (source maps)
    if filename_lower.endswith((".map", ".js.map", ".css.map")):
        return True
    
    # Skip lock files (not code)
    if filename in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Pipfile.lock", "poetry.lock"}:
        return True
    
    # Skip known vendor library files (with or without version suffix)
    # e.g., "jquery-3.6.0.js", "bootstrap.js", "react.production.min.js"
    stem = Path(filename).stem.lower()
    # Strip version suffixes: "jquery-3.6.0" -> "jquery", "bootstrap.min" -> "bootstrap"
    base_stem = re.split(r"[-.](?:\d|min|prod|production|development|slim|esm|umd|cjs)", stem)[0]
    if base_stem in _KNOWN_VENDOR_STEMS:
        return True
    
    # Skip auto-generated code files (common across frameworks)
    _GENERATED_SUFFIXES = (
        ".Designer.cs",      # WinForms auto-generated
        ".g.cs",             # WPF auto-generated
        ".g.i.cs",           # WPF incremental
        ".AssemblyInfo.cs",  # .NET assembly info
        ".designer.vb",      # VB.NET auto-generated
        ".pb.go",            # Protobuf Go
        ".pb.cc",            # Protobuf C++
        ".pb.h",             # Protobuf C++ header
        ".g.dart",           # Dart generated
        "_generated.rs",     # Rust generated
        ".auto.ts",          # TypeScript auto-generated
        ".generated.ts",     # TypeScript generated
        ".gen.go",           # Go generated
    )
    if any(filename.endswith(sfx) for sfx in _GENERATED_SUFFIXES):
        return True
    
    # Skip files with "auto-generated" markers in common naming patterns
    if filename_lower.startswith(("generated_", "auto_generated_", "autogenerated_")):
        return True
    
    return False


def classify_path(path: str) -> str:
    """
    Classify a file path into categories.
    
    Categories (in priority order):
    - "test": Test files and directories
    - "docs": Documentation
    - "data": Data files
    - "config": Configuration files
    - "example": Example/demo/tutorial code
    - "code": Production source code
    - "other": Everything else
    """
    normalized = path.strip().lstrip("/")
    parts = normalized.split("/")
    filename = parts[-1] if parts else normalized
    lower_parts = {part.lower() for part in parts}
    filename_lower = filename.lower()
    extension = Path(filename).suffix.lower()

    # 1. Test files (highest priority - always exclude from debt analysis)
    if lower_parts & TEST_DIRS:
        return "test"
    # Test file naming patterns (ALL LANGUAGES)
    test_patterns = [
        # Python
        'test_', '_test.py', 'conftest.py',
        # JavaScript/TypeScript
        '.test.js', '.test.ts', '.test.jsx', '.test.tsx',
        '.spec.js', '.spec.ts', '.spec.jsx', '.spec.tsx',
        'jest.config', 'vitest.config', 'cypress.config', 'playwright.config',
        # Go
        '_test.go',
        # Java/Kotlin
        'test.java', 'tests.java', 'test.kt',
        # Ruby
        '_spec.rb', '_test.rb',
        # Rust (tests/ dir already covered)
        # C#
        'test.cs', 'tests.cs',
    ]
    if any(pattern in filename_lower for pattern in test_patterns):
        return "test"
    # Java/Maven convention: src/test/
    if 'src/test/' in normalized.lower() or 'src\\test\\' in normalized.lower():
        return "test"
    
    # 2. Documentation
    if lower_parts & DOC_DIRS or extension in DOC_EXTENSIONS:
        return "docs"
    
    # 3. Example/demo/tutorial code (not production)
    if lower_parts & EXAMPLE_DIRS:
        return "example"
    
    # 4. Data files
    if lower_parts & DATA_DIRS or extension in DATA_EXTENSIONS:
        return "data"
    
    # 5. Config files
    if extension in CONFIG_EXTENSIONS or filename in {
        "package.json",
        "package-lock.json",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "requirements.txt",
        "Makefile",
        "Dockerfile",
        ".gitignore",
        ".eslintrc",
        ".prettierrc",
        "tsconfig.json",
        "babel.config.js",
        "webpack.config.js",
        "vite.config.js",
        "jest.config.js",
    }:
        return "config"
    
    # 6. Production code
    if extension in CODE_EXTENSIONS:
        return "code"
    
    return "other"


# Language detection mapping
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".swift": "swift",
    ".lua": "lua",
    ".sh": "shell",
    ".bat": "batch",
    ".ps1": "powershell",
}


def detect_language(path: str) -> str:
    """Detect programming language from file path."""
    suffix = Path(path).suffix.lower()
    return LANGUAGE_MAP.get(suffix, "other")


def get_language_extension(language: str) -> str:
    """Get file extension for a language."""
    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "go": ".go",
        "rust": ".rs",
        "ruby": ".rb",
        "java": ".java",
        "kotlin": ".kt",
        "scala": ".scala",
        "cpp": ".cpp",
        "c": ".c",
        "csharp": ".cs",
        "php": ".php",
        "swift": ".swift",
        "lua": ".lua",
        "shell": ".sh",
    }
    return ext_map.get(language, ".txt")
