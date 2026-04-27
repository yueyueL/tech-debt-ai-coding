"""
AI Actors configuration - GitHub actor.login patterns.
Works for ALL dates (including after October 2025).

RULES:
1. Only include REAL AI coding agents that WRITE code
2. Do NOT include: dependency updaters, formatters, security scanners,
   documentation tools, deployment platforms, or SDKs
3. Actor patterns should be exact match (actor.login field)
4. Prefer [bot] suffix patterns - these are verified GitHub App accounts
5. Non-[bot] actors (like "Copilot", "openhands") need extra verification
"""
from typing import Dict, List

AI_ACTORS = {
    # =========================================================================
    # HIGH CONFIDENCE - Major AI Coding Agents
    # These are the primary tools that autonomously write/commit code
    # =========================================================================
    "copilot": {
        "name": "GitHub Copilot",
        # NOTE: "Copilot" without [bot] is the official actor.login for
        # GitHub Copilot's agent mode (coding agent) since early 2025.
        # Verified via PR Arena: 730K+ PRs, GitHub's own product.
        "actors": ["Copilot"],
        "confidence": "high",
    },
    "cursor": {
        "name": "Cursor",
        "actors": ["cursor[bot]"],
        "confidence": "high",
    },
    "claude": {
        "name": "Claude (Anthropic)",
        "actors": ["claude[bot]"],
        "confidence": "high",
    },
    "gemini": {
        "name": "Gemini Code Assist / Jules",
        # google-labs-jules[bot] is Google's async coding agent (Jules)
        # gemini-code-assist[bot] is Gemini Code Assist for PRs
        # gemini-cli[bot] is Gemini CLI tool
        "actors": ["gemini-code-assist[bot]", "gemini-cli[bot]", "google-labs-jules[bot]"],
        "confidence": "high",
    },
    "codex": {
        "name": "OpenAI Codex",
        # chatgpt-codex-connector[bot] is the GitHub App for OpenAI Codex
        "actors": ["chatgpt-codex-connector[bot]"],
        "confidence": "high",
    },
    "devin": {
        "name": "Devin (Cognition)",
        "actors": ["devin-ai-integration[bot]"],
        "confidence": "high",
    },
    "amazon_q": {
        "name": "Amazon Q Developer",
        "actors": ["amazon-q-developer[bot]", "amazon-codecatalyst[bot]"],
        "confidence": "high",
    },
    "aider": {
        "name": "Aider",
        # aider-chat-bot is used as committer in GitHub Actions workflows
        # NOTE: No [bot] suffix - verified as Aider's CI committer identity
        "actors": ["aider-chat-bot"],
        "confidence": "high",
    },
    "openhands": {
        "name": "OpenHands (All-Hands AI)",
        # OpenHands is a major open-source AI agent (67.5K stars)
        # PRs authored by "openhands" are tracked by logic-star-ai/insights
        # NOTE: No [bot] suffix - uses plain username as commit author
        "actors": ["openhands-agent[bot]"],
        "confidence": "high",
    },

    # =========================================================================
    # MEDIUM CONFIDENCE - AI Code Assistants & Specialized Agents
    # These do write code, but may have narrower scope (reviews, fixes, etc.)
    # =========================================================================
    "coderabbit": {
        "name": "CodeRabbit AI",
        "actors": ["coderabbitai[bot]"],
        "confidence": "medium",
    },
    "lovable": {
        "name": "Lovable Dev",
        # gpt-engineer-app[bot] is also used by Lovable (formerly GPT Engineer)
        "actors": ["lovable-dev[bot]", "gpt-engineer-app[bot]"],
        "confidence": "medium",
    },
    "sourcery": {
        "name": "Sourcery AI",
        "actors": ["sourcery-ai[bot]"],
        "confidence": "medium",
    },
    "bolt": {
        "name": "Bolt (StackBlitz)",
        # NOTE: mend-bolt-for-github is a DIFFERENT product (Mend security scanner)
        "actors": ["bolt-new-by-stackblitz[bot]", "stackblitz[bot]"],
        "confidence": "medium",
    },
    "codegen": {
        "name": "Codegen.sh",
        # codegen-sh[bot] is the GitHub App
        # "codegen-sh" (no [bot]) is also used as PR author
        "actors": ["codegen-sh[bot]"],
        "confidence": "medium",
    },
    "augment": {
        "name": "Augment Code",
        "actors": ["augmentcode[bot]"],
        "confidence": "medium",
    },
    "qodo": {
        "name": "Qodo (CodiumAI)",
        "actors": ["qodo-code-review[bot]"],
        "confidence": "medium",
    },
    "codeant": {
        "name": "CodeAnt AI",
        "actors": ["codeant-ai[bot]"],
        "confidence": "medium",
    },
    "codeflash": {
        "name": "CodeFlash AI",
        "actors": ["codeflash-ai[bot]"],
        "confidence": "medium",
    },
    "ellipsis": {
        "name": "Ellipsis Dev",
        "actors": ["ellipsis-dev[bot]"],
        "confidence": "medium",
    },
    "cosine": {
        "name": "Cosine AI (Genie)",
        "actors": ["cosineai[bot]"],
        "confidence": "medium",
    },
    "deepsource": {
        "name": "DeepSource AutoFix",
        # DeepSource uses AI to auto-fix code quality issues
        "actors": ["deepsource-autofix[bot]"],
        "confidence": "medium",
    },
    "gitauto": {
        "name": "GitAuto AI",
        "actors": ["gitauto-ai[bot]"],
        "confidence": "medium",
    },
    "continue": {
        "name": "Continue.dev",
        "actors": ["continue[bot]"],
        "confidence": "medium",
    },
    "factory": {
        "name": "Factory AI (Droids)",
        # Factory's Droid AI agent for code generation
        "actors": ["factory-ai[bot]"],
        "confidence": "medium",
    },

    # =========================================================================
    # LOW CONFIDENCE - Niche / Less Common AI Agents
    # =========================================================================
    "n8n": {
        "name": "n8n Assistant",
        "actors": ["n8n-assistant[bot]"],
        "confidence": "low",
    },
    "penify": {
        "name": "Penify Dev",
        "actors": ["penify-dev[bot]"],
        "confidence": "low",
    },
    "genspark": {
        "name": "Genspark AI",
        "actors": ["genspark-ai-developer[bot]"],
        "confidence": "low",
    },
    "entelligence": {
        "name": "Entelligence AI",
        "actors": ["entelligence-ai-pr-reviews[bot]"],
        "confidence": "low",
    },
    "dane": {
        "name": "Dane AI (Mastra)",
        "actors": ["dane-ai-mastra[bot]"],
        "confidence": "low",
    },
}


def get_all_actors() -> List[str]:
    """Get flat list of all AI actor logins."""
    actors = []
    for tool in AI_ACTORS.values():
        actors.extend(tool["actors"])
    return actors


def get_actor_to_tool_map() -> Dict[str, str]:
    """Get mapping of actor_login -> tool_id."""
    result = {}
    for tool_id, tool in AI_ACTORS.items():
        for actor in tool["actors"]:
            result[actor] = tool_id
    return result
