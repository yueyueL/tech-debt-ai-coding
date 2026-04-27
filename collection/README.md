# AI-Code Collector

Unified tool for discovering and analyzing AI-authored code from GitHub.

## Features

- **Discover**: Find AI-authored repos across GitHub using BigQuery (GitHub Archive)
- **Scan**: Deep scan individual repos for AI commits using git clone or GitHub API
- **Batch Scan**: Scan multiple repos from discover results in one command
- **Metadata**: Enrich discovered repos with stars, language, and description

## Project Structure

```
collection/
├── main.py                 # CLI entry point (discover, scan, batch-scan, metadata)
├── config/
│   ├── actors.py           # GitHub actor.login patterns (35+ AI bots)
│   └── tools.py            # Commit author patterns (25+ AI tools)
├── detection/
│   ├── sql.py              # BigQuery SQL generation
│   └── scanner.py          # Commit scanning detection
├── collectors/
│   ├── bigquery.py         # BigQuery collector (discover repos)
│   ├── github.py           # GitHub API commit fetcher
│   ├── git_commits.py      # Git clone commits scanner
│   └── github_commits.py   # GitHub API commits scanner
├── models/
│   └── data.py             # Data models (RepoStats, AICommit, etc.)
├── tests/
│   ├── test_detection.py   # Detection pattern tests (28 tests)
│   └── audit_patterns.py   # False positive audit
├── utils.py                # JSON/CSV I/O utilities
├── fetch_metadata_loop.sh  # Auto-retry metadata fetch (nohup)
├── (result/)               # Auto-created at runtime — not in repo
└── requirements.txt
```

## Installation

```bash
pip install -r requirements.txt

# For BigQuery discovery
gcloud auth application-default login

# For GitHub API operations
export GITHUB_TOKEN=your_token_here
```

## Quick Start

### 1. Discover AI Repos (BigQuery)

```bash
# Test one month with limit
python3 main.py discover --start-date 2024-01-01 --end-date 2024-01-31 --limit 100

# Full year collection (auto-resumes from checkpoint)
python3 main.py discover --start-date 2024-01-01 --end-date 2024-12-31

# Show query without running (dry run)
python3 main.py discover --dry-run

# With metadata enrichment at the end
python3 main.py discover --start-date 2024-01-01 --end-date 2024-12-31 --fetch-metadata
```

### 2. Scan a Specific Repo

```bash
# Scan with GitHub API
python3 main.py scan n8n-io/n8n

# Scan with git clone (no rate limits)
python3 main.py scan n8n-io/n8n --git-clone

# With date filter
python3 main.py scan Aider-AI/aider --since 2024-01-01

# Custom output file
python3 main.py scan cline/cline -o result/cline_commits.json
```

### 3. Batch Scan Repos from Discover Results

```bash
# Scan all repos from discover output (auto-skips already scanned)
python3 main.py batch-scan result/ai_repos.json

# Only repos with >= 100 stars
python3 main.py batch-scan result/ai_repos.json --min-stars 100

# Only repos with copilot commits, top 50
python3 main.py batch-scan result/ai_repos.json --tool copilot --limit 50

# Force re-scan even if output exists
python3 main.py batch-scan result/ai_repos.json --force

# With date filter and commit limit
python3 main.py batch-scan result/ai_repos.json --since 2024-01-01 --max-commits 5000
```

### 4. Fetch Metadata for Discovered Repos

```bash
# Enrich repos with stars, language, description
python3 main.py metadata result/ai_repos.json

# Auto-retry loop (handles rate limits, runs every hour)
./fetch_metadata_loop.sh result/ai_repos.json
```

### Global Options

```bash
# Verbose logging (debug level)
python3 main.py -v discover --start-date 2024-01-01 --end-date 2024-01-31

# Log to file (useful for long-running jobs)
python3 main.py --log-file collect.log discover --start-date 2024-01-01 --end-date 2024-12-31
```

## Running Tests

```bash
# Detection pattern tests (28 test cases)
python3 tests/test_detection.py

# Pattern audit (false positive analysis)
python3 tests/audit_patterns.py
```

## AI Tools Detected

### High Confidence
- GitHub Copilot
- Claude (Anthropic)
- Cursor Agent
- Gemini Code Assist
- Amazon Q Developer
- Devin (Cognition)
- Aider
- CodeRabbit
- Blackbox AI

### Medium Confidence
- Lovable Dev
- Bolt (StackBlitz)
- Codeium / Windsurf
- Continue.dev
- Sourcery AI
- Sweep AI
- Cline
- v0 by Vercel
- And 15+ more...

## Output Formats

Results are saved in both JSON and CSV formats:

### JSON Structure (discover)
```json
{
  "stats": {"gb_processed": 45.2, "cost_estimate_usd": 0.23},
  "last_updated": "2024-12-31T23:59:59",
  "repos": [
    {
      "full_name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "stars": 1234,
      "language": "Python",
      "commit_counts": {"copilot": 50, "claude": 10},
      "detection_methods": {"copilot": "actor", "claude": "coauthor"}
    }
  ]
}
```

### JSON Structure (scan / batch-scan)
```json
{
  "repo": "owner/repo",
  "total_commits_scanned": 5000,
  "ai_commits_count": 42,
  "tools_found": {"copilot": 30, "claude": 12},
  "ai_commits": [
    {
      "sha": "abc123...",
      "ai_tool": "copilot",
      "detection_method": "coauthor",
      "author_role": "coauthor",
      "ai_identifier": "Copilot",
      "ai_identifier_type": "coauthor_name",
      "author_name": "Human Dev",
      "date": "2024-06-15T10:30:00Z",
      "url": "https://github.com/owner/repo/commit/abc123"
    }
  ]
}
```

## Detection Methods

1. **actor.login** - GitHub bot account that pushed (works for all dates)
2. **author_email** - Commit author email patterns (e.g., `noreply@anthropic.com`)
3. **author_name** - Commit author name patterns (e.g., `cursoragent`)
4. **coauthor** - Co-authored-by trailer in commit message
5. **committer** - Git committer (for workflows like Aider)

## Checkpointing & Resume

The discover command saves progress after each month:
- **Checkpoint file**: `result/ai_repos.checkpoint.json` tracks completed months
- **Auto-resume**: Re-running the same date range skips already-collected months
- **Crash-safe**: Results are saved after every month, so interrupted runs lose at most 1 month

The batch-scan command skips repos that already have output files (unless `--force` is used).

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | discover | Path to GCP service account JSON |
| `GITHUB_TOKEN` | scan/metadata | GitHub personal access token |

## License

MIT
