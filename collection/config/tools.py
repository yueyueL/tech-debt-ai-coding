"""
AI Tools configuration - commit author patterns.

These patterns match commit AUTHOR name/email fields in git log.
Used for:
1. BigQuery SQL (author detection in GitHub Archive commit data)
2. Local git clone scanning (commit author/committer matching)
3. Co-authored-by trailer matching in commit messages

STRICT RULES TO AVOID FALSE POSITIVES:
1. NEVER use common person names alone: Cody, Devin, etc.
2. NEVER use short/common words: v0, bolt, cline, pieces, sweep
3. Use [bot] suffix when possible - these are GitHub bot accounts
4. Use specific email domains: @cursor.com, @aider.chat, @v0.dev
5. For author_email_like: ALWAYS include @ to anchor to a domain
6. Do NOT match human employees even from AI companies
7. When in doubt, leave it out - better to miss than false positive

PATTERN TYPES:
- author_email: Exact email match (case-insensitive substring)
- author_email_like: SQL LIKE pattern (% = wildcard), MUST contain @
- author_name: Exact match for primary author, startswith for coauthor
"""

AI_TOOLS = {
    # =========================================================================
    # HIGH CONFIDENCE - Major AI Coding Tools
    # Distinctive, verified patterns with very low false positive risk
    # =========================================================================
    "claude": {
        "name": "Claude (Anthropic)",
        "vendor": "Anthropic",
        "patterns": {
            # noreply@anthropic.com is the primary official email (452 real commits)
            # claude@anthropic.ai is an alternate domain (106 real commits)
            "author_email": ["noreply@anthropic.com", "claude@anthropic.ai"],
            # GitHub App email pattern: 209825114+claude[bot]@users.noreply.github.com
            "author_email_like": ["%+claude[bot]@users.noreply.github.com"],
            # REMOVED bare "Claude" - it's a human name (Claude Shannon, etc.)
            # Real Claude commits ALWAYS have @anthropic.com or @anthropic.ai email
            # claude[bot] is the verified GitHub App account - safe
            "author_name": ["claude[bot]"],
        },
        "confidence": "high",
    },
    "cursor": {
        "name": "Cursor Agent",
        "vendor": "Cursor",
        "patterns": {
            "author_email": ["cursoragent@cursor.com"],
            "author_name": ["cursoragent", "Cursor Agent", "cursor[bot]"],
        },
        "confidence": "high",
    },
    "copilot": {
        "name": "GitHub Copilot",
        "vendor": "GitHub/Microsoft",
        "patterns": {
            "author_email": ["Copilot@users.noreply.github.com"],
            # Anchored to noreply.github.com domain - safe
            # copilot-swe-agent[bot] has 3100 real commits via this pattern
            "author_email_like": ["%copilot%@users.noreply.github.com",
                                  "%copilot-swe-agent%@users.noreply.github.com"],
            "author_name": [
                "Copilot",
                "copilot-bot",
                "copilot[bot]",
                "GitHub Copilot",
                "Copilot Autofix powered by AI",
                "github-advanced-security[bot]",
                "copilot-swe-agent[bot]",
            ],
        },
        "confidence": "high",
    },
    "gemini": {
        "name": "Gemini Code Assist",
        "vendor": "Google",
        "patterns": {
            # gemini-cli-robot@google.com found in real data (3 commits)
            "author_email": ["gemini-cli-robot@google.com"],
            # GitHub App emails for Gemini bots + code-assist pattern
            "author_email_like": ["%gemini-code-assist%@%",
                                  "%+gemini-cli[bot]@users.noreply.github.com",
                                  "%+google-labs-jules[bot]@users.noreply.github.com"],
            "author_name": [
                "gemini-code-assist",
                "Gemini Code Assist",
                "gemini[bot]",
                "gemini-code-assist[bot]",
                "gemini-cli[bot]",
                "google-labs-jules[bot]",
            ],
        },
        "confidence": "high",
    },
    "devin": {
        "name": "Devin",
        "vendor": "Cognition AI",
        "patterns": {
            # STRICT: Only match @devin.ai domain, NOT person names
            # Also match the GitHub App email (3095 real commits)
            "author_email_like": ["%@devin.ai",
                                  "%+devin-ai-integration[bot]@users.noreply.github.com"],
            # Do NOT use "Devin" alone - it's a very common person name!
            "author_name": ["devin-ai-integration[bot]", "Devin AI", "cognition-devin[bot]"],
        },
        "confidence": "high",
    },
    "amazon_q": {
        "name": "Amazon Q Developer",
        "vendor": "Amazon",
        "patterns": {
            # Anchored to @amazon domain - safe
            "author_email_like": ["%amazon-q%@amazon%", "%amazonq%@amazon%"],
            "author_name": [
                "Amazon Q",
                "amazon-q[bot]",
                "amazonq[bot]",
                "amazon-q-developer[bot]",
                "amazon-codecatalyst[bot]",
            ],
        },
        "confidence": "high",
    },
    "aider": {
        "name": "Aider",
        "vendor": "Aider",
        "patterns": {
            "author_email": ["noreply@aider.chat"],
            "author_email_like": ["%@aider.chat"],
            # "aider" is not a common person name - relatively safe
            "author_name": ["aider", "Aider", "aider-chat-bot"],
        },
        "confidence": "high",
    },
    "blackbox": {
        "name": "Blackbox AI",
        "vendor": "Blackbox",
        "patterns": {
            # STRICT: Only match blackboxai.com / useblackbox.io domains
            # Do NOT use %blackbox% - matches blackbox.lan, blackbox.(none), etc.
            "author_email_like": ["%@blackboxai.com", "%@useblackbox.io"],
            "author_name": ["blackboxai-deploy[bot]", "Blackbox AI", "blackboxai[bot]"],
        },
        "confidence": "high",
    },
    "coderabbit": {
        "name": "CodeRabbit",
        "vendor": "CodeRabbit",
        "patterns": {
            # Anchored to @ - safe
            "author_email_like": ["%@coderabbit%", "%coderabbitai%@%"],
            "author_name": ["coderabbitai[bot]", "CodeRabbit", "coderabbit[bot]"],
        },
        "confidence": "high",
    },
    "openhands": {
        "name": "OpenHands",
        "vendor": "All-Hands AI",
        "patterns": {
            "author_email_like": ["%@all-hands.dev"],
            "author_name": ["openhands-agent[bot]", "OpenHands"],
        },
        "confidence": "high",
    },

    # =========================================================================
    # MEDIUM CONFIDENCE - Known AI Tools
    # Patterns are specific but smaller user base = less verification
    # =========================================================================
    "codex": {
        "name": "OpenAI Codex",
        "vendor": "OpenAI",
        "patterns": {
            "author_email": ["codex@openai.com"],
            "author_email_like": ["%codex%@openai%"],
            "author_name": ["OpenAI Codex", "openai-codex", "codex[bot]",
                           "chatgpt-codex-connector[bot]"],
        },
        "confidence": "medium",
    },
    "codeium": {
        "name": "Codeium",
        "vendor": "Codeium",
        "patterns": {
            "author_email_like": ["%@codeium.com"],
            "author_name": ["codeium[bot]", "Codeium AI"],
        },
        "confidence": "medium",
    },
    "windsurf": {
        "name": "Windsurf",
        "vendor": "Codeium",
        "patterns": {
            # Anchored to @codeium domain - safe
            "author_email_like": ["%windsurf%@codeium%"],
            "author_name": ["Windsurf AI", "windsurf[bot]"],
        },
        "confidence": "medium",
    },
    "tabnine": {
        "name": "Tabnine",
        "vendor": "Tabnine",
        "patterns": {
            "author_email_like": ["%@tabnine.com"],
            "author_name": ["tabnine[bot]", "Tabnine AI"],
        },
        "confidence": "medium",
    },
    "cody": {
        "name": "Sourcegraph Cody",
        "vendor": "Sourcegraph",
        "patterns": {
            # STRICT: Must have cody AND sourcegraph in email
            # REMOVED: "%@sourcegraph.com" - matches ALL Sourcegraph employees!
            "author_email_like": ["%cody%@sourcegraph%"],
            # Do NOT use "Cody" alone - it's a common person name!
            "author_name": ["sourcegraph-cody[bot]", "cody[bot]", "Cody AI"],
        },
        "confidence": "medium",
    },
    "replit": {
        "name": "Replit Agent",
        "vendor": "Replit",
        "patterns": {
            # STRICT: Only match replit-agent-specific email
            # REMOVED: "%agent%@replit.com" - could match human agent roles
            "author_email_like": ["%replit-agent%@replit.com"],
            "author_name": ["Replit Agent", "replit-agent[bot]", "replit[bot]"],
        },
        "confidence": "medium",
    },
    "continue": {
        "name": "Continue.dev",
        "vendor": "Continue",
        "patterns": {
            "author_email_like": ["%@continue.dev"],
            "author_name": ["Continue AI", "continue[bot]"],
        },
        "confidence": "medium",
    },
    "sweep": {
        "name": "Sweep AI",
        "vendor": "Sweep",
        "patterns": {
            # Anchored to specific domains
            "author_email_like": ["%@sweep.dev", "%sweepai%@%"],
            "author_name": ["sweep[bot]", "Sweep AI"],
        },
        "confidence": "medium",
    },
    "lovable": {
        "name": "Lovable Dev",
        "vendor": "Lovable",
        "patterns": {
            "author_email_like": ["%@lovable.dev", "%@lovable.app"],
            # lovable-dev[bot] and gpt-engineer-app[bot] are verified GitHub bot accounts
            # REMOVED: bare "Lovable" - it's an adjective, could be username
            "author_name": ["Lovable AI", "lovable[bot]", "lovable-dev[bot]",
                           "gpt-engineer-app[bot]"],
        },
        "confidence": "medium",
    },
    "bolt": {
        "name": "Bolt (StackBlitz)",
        "vendor": "StackBlitz",
        "patterns": {
            # STRICT: Only match bolt.new or stackblitz.com domains
            "author_email_like": ["%@bolt.new", "%@stackblitz.com"],
            # Do NOT use "bolt" alone - matches mend-bolt, thunderbolt, etc.
            "author_name": ["ProjectBolt Dev", "bolt.new[bot]", "stackblitz[bot]",
                           "bolt-new-by-stackblitz[bot]"],
        },
        "confidence": "medium",
    },
    "cline": {
        "name": "Cline",
        "vendor": "Cline",
        "patterns": {
            # STRICT: Only match cline.bot domain
            "author_email_like": ["%@cline.bot"],
            # Do NOT use "cline" alone - matches usernames like SeanCline!
            "author_name": ["cline[bot]", "Cline AI"],
        },
        "confidence": "medium",
    },
    "v0": {
        "name": "v0 by Vercel",
        "vendor": "Vercel",
        "patterns": {
            # STRICT: Only match v0.dev domain
            "author_email_like": ["%@v0.dev"],
            # Do NOT use "v0" alone - matches v0idpwn, v0x, v01d, etc.
            "author_name": ["v0[bot]", "v0 by Vercel", "v0.dev[bot]"],
        },
        "confidence": "medium",
    },
    "supermaven": {
        "name": "Supermaven",
        "vendor": "Supermaven",
        "patterns": {
            "author_email_like": ["%@supermaven.com"],
            "author_name": ["supermaven[bot]", "Supermaven AI"],
        },
        "confidence": "medium",
    },
    "phind": {
        "name": "Phind",
        "vendor": "Phind",
        "patterns": {
            "author_email_like": ["%@phind.com"],
            "author_name": ["Phind AI", "phind[bot]"],
        },
        "confidence": "medium",
    },
    "pieces": {
        "name": "Pieces",
        "vendor": "Pieces",
        "patterns": {
            "author_email_like": ["%@pieces.app"],
            "author_name": ["Pieces AI", "pieces[bot]"],
        },
        "confidence": "medium",
    },

    # =========================================================================
    # REMOVED (too risky / not AI coding agents):
    #
    # vercel_bot: "%bot%@vercel.com" matches any Vercel bot/employee
    #             "nextjs-bot", "Turbobot" are build bots, not AI coding
    #
    # gitpod: "%bot%@gitpod.io" too broad, matches employees
    #         Gitpod is a cloud IDE, not an AI coding agent
    # =========================================================================
}
