"""
Commit scanner for AI detection.

Returns detection info including:
- tool_key: The AI tool detected (e.g., "claude", "copilot")
- detection_method: How detected (e.g., "author_name", "coauthor")
- ai_identifier: The specific pattern that matched (e.g., "claude[bot]")
- ai_identifier_type: Type of identifier (e.g., "author_name", "author_email")
"""
import re
from typing import Optional, Tuple, Dict, Any

from config.actors import AI_ACTORS, get_actor_to_tool_map
from config.tools import AI_TOOLS


# Detection result type: (tool_key, detection_method, ai_identifier, ai_identifier_type)
DetectionResult = Optional[Tuple[str, str, str, str]]


def detect_ai_from_actor(actor_login: str) -> DetectionResult:
    """
    Detect AI tool from GitHub actor login.
    
    Returns:
        Tuple of (tool_key, detection_method, ai_identifier, ai_identifier_type) or None
    """
    actor_map = get_actor_to_tool_map()
    if actor_login in actor_map:
        return (actor_map[actor_login], "actor", actor_login, "actor")
    return None


def detect_ai_from_author(author_name: str, author_email: str, partial_match: bool = False) -> DetectionResult:
    """
    Detect AI tool from commit author name/email.
    
    Args:
        author_name: Git commit author name
        author_email: Git commit author email
        partial_match: If True, use substring matching for names (for coauthor detection)
    
    Returns:
        Tuple of (tool_key, detection_method, ai_identifier, ai_identifier_type) or None
    """
    author_name_lower = author_name.lower() if author_name else ""
    author_email_lower = author_email.lower() if author_email else ""
    
    # First check AI_TOOLS patterns
    for tool_key, tool_config in AI_TOOLS.items():
        patterns = tool_config.get("patterns", {})
        
        # Check author email exact match
        for email_pattern in patterns.get("author_email", []):
            if email_pattern.lower() in author_email_lower:
                return (tool_key, "author_email", email_pattern, "author_email")
        
        # Check author email LIKE pattern
        for email_like in patterns.get("author_email_like", []):
            # Convert SQL LIKE to regex:
            # 1. Escape regex special chars (like [bot] -> \[bot\])
            # 2. Then convert % wildcards to .*
            escaped = re.escape(email_like.lower())
            pattern = escaped.replace(re.escape("%"), ".*")
            if re.search(pattern, author_email_lower):
                return (tool_key, "author_email", email_like, "author_email_like")
        
        # Check author name
        for name_pattern in patterns.get("author_name", []):
            name_pattern_lower = name_pattern.lower()
            if partial_match:
                # For coauthor detection: "aider (openai/gpt-4)" starts with "aider"
                if author_name_lower.startswith(name_pattern_lower):
                    return (tool_key, "author_name", name_pattern, "author_name")
            else:
                # For primary author: exact match only
                if name_pattern_lower == author_name_lower:
                    return (tool_key, "author_name", name_pattern, "author_name")
    
    # Also check AI_ACTORS (for git clone mode where bot appears as author)
    # Only do exact match for actors
    if not partial_match:
        for tool_key, actor_config in AI_ACTORS.items():
            for actor_name in actor_config.get("actors", []):
                if actor_name.lower() == author_name_lower:
                    return (tool_key, "author_name", actor_name, "actor_as_author")
    
    return None


def detect_ai_from_coauthor(commit_message: str) -> DetectionResult:
    """
    Detect AI tool from Co-authored-by in commit message.
    
    Returns:
        Tuple of (tool_key, detection_method, ai_identifier, ai_identifier_type) or None
    """
    if not commit_message:
        return None
    
    # Look for Co-authored-by patterns
    coauthor_pattern = r"Co-authored-by:\s*([^<]+)\s*<([^>]+)>"
    matches = re.findall(coauthor_pattern, commit_message, re.IGNORECASE)
    
    for name, email in matches:
        name = name.strip()
        email = email.strip()
        result = detect_ai_from_author(name, email, partial_match=True)
        if result:
            tool_key, method, ai_identifier, ai_id_type = result
            # Update the identifier type to indicate it came from coauthor
            if ai_id_type == "author_email" or ai_id_type == "author_email_like":
                return (tool_key, "coauthor", ai_identifier, "coauthor_email")
            else:
                return (tool_key, "coauthor", ai_identifier, "coauthor_name")
    
    return None


def detect_ai_commit(
    author_name: str,
    author_email: str,
    commit_message: str = "",
    actor_login: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Detect if a commit is AI-authored.
    
    Args:
        author_name: Git commit author name
        author_email: Git commit author email
        commit_message: Full commit message
        actor_login: GitHub actor (who pushed)
    
    Returns:
        Dict with detection info:
        {
            "tool_key": str,
            "detection_method": str,
            "author_role": "sole_author" | "coauthor",
            "ai_identifier": str,  # The pattern that matched
            "ai_identifier_type": str,  # Type of pattern
        }
        or None
    """
    # Priority 1: Actor-based detection (GitHub bot pushed)
    if actor_login:
        result = detect_ai_from_actor(actor_login)
        if result:
            tool_key, method, ai_identifier, ai_id_type = result
            return {
                "tool_key": tool_key,
                "detection_method": method,
                "author_role": "sole_author",  # Bot pushed = sole author
                "ai_identifier": ai_identifier,
                "ai_identifier_type": ai_id_type,
            }
    
    # Priority 2: Author-based detection (AI is the author)
    result = detect_ai_from_author(author_name, author_email)
    if result:
        tool_key, method, ai_identifier, ai_id_type = result
        return {
            "tool_key": tool_key,
            "detection_method": method,
            "author_role": "sole_author",  # AI is the commit author
            "ai_identifier": ai_identifier,
            "ai_identifier_type": ai_id_type,
        }
    
    # Priority 3: Co-author detection (AI is listed as co-author)
    result = detect_ai_from_coauthor(commit_message)
    if result:
        tool_key, method, ai_identifier, ai_id_type = result
        return {
            "tool_key": tool_key,
            "detection_method": method,
            "author_role": "coauthor",  # AI is a co-author, human is primary
            "ai_identifier": ai_identifier,
            "ai_identifier_type": ai_id_type,
        }
    
    return None


def get_tool_name(tool_key: str) -> str:
    """Get human-readable name for a tool key."""
    if tool_key in AI_TOOLS:
        return AI_TOOLS[tool_key].get("name", tool_key)
    if tool_key in AI_ACTORS:
        return AI_ACTORS[tool_key].get("name", tool_key)
    return tool_key
