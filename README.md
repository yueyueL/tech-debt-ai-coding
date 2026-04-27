# Debt Behind the AI Boom

Replication package for the paper:

> **Debt Behind the AI Boom: A Large-Scale Empirical Study of AI-Generated Code in the Wild**
> Yue Liu, Ratnadira Widyasari, Yanjie Zhao, Ivana Clairine Irsan, Junkai Chen, David Lo
> [arXiv:2603.28592](https://arxiv.org/abs/2603.28592)

We mined 302.6K AI-authored commits from 6,299 GitHub repositories across five
AI coding assistants (GitHub Copilot, Claude, Cursor, Gemini, Devin), ran static
analysis before and after each commit, and tracked whether the introduced issues
still survive in the codebase today.

**Key finding:** 484K issues were introduced; **22.7%** still survive at HEAD,
including issues introduced more than nine months earlier.

---

## Repository layout

```
tech-debt-ai-coding/
├── collection/         Phase 1 — discover and label AI-authored commits on GitHub
├── src/                Phase 2-3 — static analysis, lifecycle tracking, reporting
├── scripts/            CLI entry points (run_pipeline.py, batch_analyze.py, regenerate_issue_survival.py)
├── data/               Inputs: 6,299-repo manifest, validation labels, commit lists
├── results/out/        Outputs: per-repo metrics + aggregate_summary.json
├── main.py             Interactive menu (analyze, view results, dashboard)
└── README.md           You are here
```

The repository ships **two demo repos** (`superagent-ai/superagent` and
`microsoft/data-formulator`) so the dashboard works out of the box. The
full 6,299-repo dataset lives on Google Drive — see *Data downloads* below.

---

## Quick start (no setup, ~30 seconds)

View the paper's results in the interactive dashboard:

```bash
git clone https://github.com/yueyueL/tech-debt-ai-coding.git
cd tech-debt-ai-coding
python3 main.py
# → 5 (Open dashboard) → browser opens
```

You'll see the aggregate numbers, top rules, and per-repo browser for the two
demo repos. Hit Ctrl+C in the terminal to stop the server.

---

## Reproduction tiers

| Tier | What you do | Time | Disk | Needs |
|---|---|---|---|---|
| **T1** | Browse `results/out/aggregate_summary.json` via the dashboard (above) | <1 min | 0 GB | Python 3.10+ |
| **T2** | Re-aggregate from saved per-repo metrics | ~5 min | ~10 GB | Python 3.10+, [`results-out.zip`](#data-downloads) |
| **T3** | Re-run the full pipeline from raw commits | days | ~500 GB | Python 3.10+, Pylint, ESLint, Semgrep, git, [`commits.zip`](#data-downloads) |

### T2 — Re-aggregate

```bash
# 1. Download results-out.zip from Google Drive (see Data downloads).
#    Place it at the project root, then:
unzip results-out.zip -d results/

# 2. Re-aggregate
python3 -m src.reporting.aggregate --out-dir results/out
```

Compare the new `results/out/aggregate_summary.json` to the one shipped here.

### T3 — Full re-run from raw commits

```bash
# 1. Download commits.zip from Google Drive (see Data downloads).
#    Place it at data/commits.zip, then:
unzip data/commits.zip -d data/

# 2. Install analyzer dependencies
pip install pylint semgrep            # Python analyzers
npm install                           # JavaScript: ESLint + plugins (uses src/config/eslint.config.mjs)

# 3. Run the pipeline on one repo (smoke test, ~2 min)
python3 scripts/run_pipeline.py --input data/commits/superagent-ai_superagent_commits.json

# 4. Run on all 6,299 (very long)
python3 main.py     # → 2 (Batch analyze) → directory: data/commits
```

---

## Data downloads

The full data is too large to ship in Git. Both bundles live on Google Drive:

| Bundle | Compressed | Contents |
|---|---|---|
| `commits.zip` | ~46 MB | All 6,299 `<repo>_commits.json` files (input to T3) |
| `results-out.zip` | ~940 MB | Per-repo `debt_metrics.json`, `issue_survival.json`, `lifecycle_metrics.json`, `destiny_metrics.json`, `summary.json` and `debug/` for all 6,299 repos (input to T2) |

**Google Drive (both bundles):** <https://drive.google.com/drive/folders/1R3uiO6dt9gWEq_2njwS-ve4DawxvpsS1?usp=sharing>

After downloading, follow the **T2** / **T3** commands above to plug them in.

---

## What's in `data/`

| File | Purpose |
|---|---|
| `focused_repos.json` | Manifest of the 6,299 analyzed repos (the paper's dataset) |
| `ai_repos.csv` | Repo metadata (stars, language, primary AI tool) |
| `commits/` | 2 demo `<repo>_commits.json` files; full 6,299 in `commits.zip` |
| `validation/` | The 100+100 manually labelled samples used in §IV-D (Cohen's κ) |
| `exploratory/` | Intermediate JSON outputs from paper-example finder scripts |

See [`data/README.md`](data/README.md) for schema details.

---

## Citation

```bibtex
@article{liu2026techdebt,
  title         = {Debt Behind the AI Boom: A Large-Scale Empirical Study of
                   AI-Generated Code in the Wild},
  author        = {Liu, Yue and Widyasari, Ratnadira and Zhao, Yanjie and
                   Irsan, Ivana Clairine and Chen, Junkai and Lo, David},
  year          = {2026},
  eprint        = {2603.28592},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE}
}
```

