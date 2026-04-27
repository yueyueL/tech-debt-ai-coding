"""
Shared configuration and paths for the AI code analysis project.
"""

from pathlib import Path


# Project root directory (src/core/config.py -> src/core -> src -> project_root)
ROOT_DIR = Path(__file__).resolve().parents[2]

# Data directories
DATA_DIR = ROOT_DIR / "data"
REPO_CACHE_DIR = DATA_DIR / "repos"
RESULTS_DIR = DATA_DIR / "results"

# Output directory — analysis results live under results/out/<repo>/.
# (Reproduction-package convention. A pre-existing top-level 'out/' is still
# discovered by the dashboard as a legacy fallback.)
OUT_DIR = ROOT_DIR / "results" / "out"
DEBUG_DIR = OUT_DIR / "debug"

# Default checkpoint paths
DEFAULT_LIFECYCLE_CHECKPOINT = RESULTS_DIR / "lifecycle_checkpoint.json"
DEFAULT_PIPELINE_SETTINGS = DATA_DIR / "pipeline_settings.json"
