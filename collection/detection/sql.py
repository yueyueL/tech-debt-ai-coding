"""
SQL generation utilities for BigQuery AI detection.
"""
from config.tools import AI_TOOLS
from config.actors import AI_ACTORS


def build_author_detection_sql() -> str:
    """Build SQL CASE for author-based detection (pre-Oct 2025)."""
    conditions = []
    
    for tool_key, tool in AI_TOOLS.items():
        patterns = tool.get("patterns", {})
        
        # Exact email match
        for email in patterns.get("author_email", []):
            conditions.append(f"WHEN author_email = '{email}' THEN '{tool_key}'")
        
        # Email pattern match (LIKE)
        for pattern in patterns.get("author_email_like", []):
            conditions.append(f"WHEN author_email LIKE '{pattern}' THEN '{tool_key}'")
        
        # Author name match
        for name in patterns.get("author_name", []):
            conditions.append(f"WHEN LOWER(author_name) = LOWER('{name}') THEN '{tool_key}'")
    
    if not conditions:
        return "NULL"
    
    return "CASE\n      " + "\n      ".join(conditions) + "\n      ELSE NULL\n    END"


def build_coauthor_detection_sql() -> str:
    """Build SQL CASE for co-author detection in commit messages."""
    conditions = []
    
    for tool_key, tool in AI_TOOLS.items():
        patterns = tool.get("patterns", {})
        
        for email in patterns.get("author_email", []):
            conditions.append(
                f"WHEN commit_message LIKE '%Co-authored-by:%{email}%' THEN '{tool_key}'"
            )
        
        for name in patterns.get("author_name", []):
            conditions.append(
                f"WHEN commit_message LIKE '%Co-authored-by: {name}%' THEN '{tool_key}'"
            )
    
    if not conditions:
        return "NULL"
    
    return "CASE\n      " + "\n      ".join(conditions) + "\n      ELSE NULL\n    END"


def build_actor_detection_sql() -> str:
    """
    Build SQL CASE for actor.login-based AI detection.
    Works for ALL dates, including after Oct 2025.
    """
    conditions = []
    
    for tool_key, tool in AI_ACTORS.items():
        for actor in tool["actors"]:
            conditions.append(f"WHEN actor_login = '{actor}' THEN '{tool_key}'")
    
    if not conditions:
        return "NULL"
    
    return "CASE\n      " + "\n      ".join(conditions) + "\n      ELSE NULL\n    END"


def get_actor_where_clause() -> str:
    """Get SQL WHERE clause for filtering AI actors."""
    all_actors = []
    for tool in AI_ACTORS.values():
        all_actors.extend(tool["actors"])
    
    if not all_actors:
        return "FALSE"
    
    quoted_actors = [f"'{a}'" for a in all_actors]
    return f"actor.login IN ({', '.join(quoted_actors)})"
