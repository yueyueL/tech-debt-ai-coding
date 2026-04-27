"""AI detection configuration - actors and tools patterns."""

from .actors import AI_ACTORS, get_all_actors, get_actor_to_tool_map
from .tools import AI_TOOLS

__all__ = ["AI_ACTORS", "AI_TOOLS", "get_all_actors", "get_actor_to_tool_map"]
