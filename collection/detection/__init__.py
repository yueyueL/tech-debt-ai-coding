"""AI detection - SQL generation and commit scanning."""

from .scanner import detect_ai_commit, get_tool_name
from .sql import (
    build_author_detection_sql,
    build_coauthor_detection_sql,
    build_actor_detection_sql,
    get_actor_where_clause,
)

__all__ = [
    "detect_ai_commit",
    "get_tool_name",
    "build_author_detection_sql",
    "build_coauthor_detection_sql",
    "build_actor_detection_sql",
    "get_actor_where_clause",
]
