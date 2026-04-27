# Data

This directory holds the inputs to the analysis pipeline. Small files are
checked into the repository; large files are hosted externally and downloaded
on demand.

## In-repo files

| File / Directory | Size | What it is |
|---|---|---|
| `focused_repos.json` | 1.6 MB | Canonical manifest of the **6,299 GitHub repositories** analyzed in the paper, with stars / language / AI-commit counts per repo. This is the authoritative input for the analysis pipeline. |
| `ai_repos.csv` | ~540 KB | Repo metadata (stars, language, primary AI tool) for the same 6,299 repos. Read by `src/reporting/aggregate.py` to enrich dashboard tables. |
| `commits/<repo>_commits.json` | ~10 KB each | Per-repo commit lists (`{ai_commits: [...]}`). The repo ships **two demo files** (the repos cited in Figure 5 and Listing 3 of the paper). The full set of 6,299 commits files is available externally — see [`commits/README.md`](commits/README.md). |
| `validation/` | 460 KB | Manually labeled samples used for the Cohen's κ validation in §IV-D. See `validation/ai_identifying/` (attribution sample) and `validation/vul_check/` (issue sample). |
| `exploratory/` | small | Intermediate JSON outputs from paper-example finder scripts. Not required for reproduction, kept for transparency. |

## External data (Google Drive)

These bundles are hosted on Google Drive because they exceed GitHub's per-file
limit and would balloon the repository size.

**Google Drive (both bundles):** <https://drive.google.com/drive/folders/1R3uiO6dt9gWEq_2njwS-ve4DawxvpsS1?usp=sharing>

| Bundle | Compressed | Uncompressed | Contents |
|---|---|---|---|
| `commits.zip` | ~46 MB | ~265 MB | All 6,299 `<repo>_commits.json` files. Required for **Tier 3** (full re-run from raw commits). |
| `results-out.zip` | ~940 MB | ~17 GB | Per-repo `debt_metrics.json`, `issue_survival.json`, `lifecycle_metrics.json`, `destiny_metrics.json`, `summary.json` and `debug/` for all 6,299 repos. Required for **Tier 2** (re-aggregate from saved analyzer output). |

The `aggregate_summary.json` already in [`../results/out/`](../results/out/)
covers **Tier 1** (verify the paper's headline numbers); no external download
needed for that.

## Schema notes

### `focused_repos.json`

```json
{
  "description": "...",
  "total_repos": 6299,
  "repos": [
    {
      "repo": "owner/name",
      "file": "data/commits/owner_name_commits.json",
      "stars": 12345,
      "language": "Python",
      "ai_commits": 42,
      "total_commits": 5000,
      "ai_percentage": 0.84
    }
  ]
}
```

### `commits/<owner>_<repo>_commits.json`

```json
{
  "repo": "owner/name",
  "total_commits_scanned": 5000,
  "ai_commits_count": 42,
  "tools_found": {"copilot": 30, "claude": 12},
  "ai_commits": [
    {
      "sha": "abc123...",
      "ai_tool": "copilot",
      "detection_method": "coauthor",
      "author_role": "coauthor",
      "author_name": "Human Dev",
      "date": "2025-06-15T10:30:00Z",
      "url": "https://github.com/owner/name/commit/abc123"
    }
  ]
}
```

### Validation samples

`validation/ai_identifying/attribution_sample.{json,csv}` — 100 commits
sampled at random from the dataset for AI-attribution validation.
99/100 verifiable; 99/99 confirmed correct after manual inspection
(see paper §IV-D, "Validation").

`validation/vul_check/issue_sample.{json,csv}` — 100 issues sampled for
issue-validity and survival-classification checks. Two reviewers each
labelled 99/99 verifiable cases. Cohen's κ = 0.85 (issue validity) and
0.96 (survival classification).
