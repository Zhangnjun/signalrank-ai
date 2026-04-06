# SignalRank AI

中文文档: [README.zh-CN.md](./README.zh-CN.md)

SignalRank AI is a configurable AI industry intelligence monitor.

Given a resume or CV, it collects fresh AI news, lab announcements, engineering blogs, and research feeds, then ranks each item by:

- resume relevance
- industry impact
- content quality
- discovery value

The goal is not to build a generic news crawler. The goal is to surface AI developments that are either:

- highly aligned with a person's background
- genuinely important to the broader AI industry

This makes it useful for engineers, researchers, job seekers, and technical operators who want a focused signal layer instead of a noisy feed dump.

## Why This Project

Most AI news monitoring setups fail in one of two ways:

- they hardcode keywords and become brittle
- they collect too much low-quality hype and bury the useful items

SignalRank AI takes a different approach:

- it derives a profile from the CV itself instead of relying on a fixed keyword list
- it scores each item across multiple dimensions instead of using a single filter
- it supports a two-stage AI rerank flow: local recall first, AI refinement second

## Features

- Resume-driven relevance scoring from `txt`, `md`, `pdf`, and `docx`
- Config-driven source ingestion via `rss`, `atom`, and `json_feed`
- HTML cleanup and article body extraction
- URL-level and topic-level deduplication
- Local scoring for:
  - `relevance_score`
  - `impact_score`
  - `quality_score`
  - `discovery_score`
  - `final_score`
- Optional OpenAI-powered rerank:
  - embedding-based semantic rerank
  - LLM-based final structured judgment
- Markdown and JSON outputs for both human review and downstream automation

## Repository Layout

```text
signalrank-ai/
├── .gitignore
├── README.md
├── pyproject.toml
├── sources.example.json
├── sources.curated.json
├── sources.premium.example.json
└── src/ai_hotspot_monitor
    ├── cli.py
    ├── config.py
    ├── fetcher.py
    ├── models.py
    ├── pipeline.py
    ├── resume.py
    └── scoring.py
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp sources.curated.json sources.json
```

Run a local-only pass:

```bash
ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json
```

Run with AI rerank enabled:

```bash
export OPENAI_API_KEY="your_key"

ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json \
  --ai-evaluate \
  --embedding-model text-embedding-3-small \
  --ai-candidate-pool 20 \
  --ai-top-k 8 \
  --ai-model gpt-5-mini
```

## Source Configurations

This repository includes three source presets:

- `sources.example.json`
  A minimal starter configuration.
- `sources.curated.json`
  A practical set of validated public feeds suitable for direct use.
- `sources.premium.example.json`
  A template for premium or restricted sources such as The Information, Semafor, or sources that may require cookies, authentication, or custom scraping.

You can add more sources without touching the pipeline code.

## Output

Reports are written to `./reports` by default:

- `ai_hotspots_<timestamp>.json`
- `ai_hotspots_<timestamp>.md`

Each record includes:

- title, source, publish time, and URL
- generated summary
- matched resume terms
- local scores
- final scores
- optional embedding score
- keep decision and keep reason
- heavyweight-event flag

## How It Works

### 1. Resume Profiling

The resume is normalized and converted into a lightweight profile:

- normalized text
- salient terms
- a short focus summary

This allows the system to adapt to different CVs instead of using a fixed keyword list.

### 2. Collection and Cleanup

Configured feeds are fetched, parsed, and cleaned.
The crawler attempts to extract article bodies while degrading gracefully when pages return `403`, `404`, or weak HTML.

### 3. Deduplication and Topic Grouping

The pipeline removes duplicate URLs and groups similar titles into topic clusters.
This helps avoid overweighting the same story across multiple sources.

### 4. Local Scoring

Each item is scored across multiple dimensions:

- `relevance_score`
  CV similarity using TF-IDF character features, term overlap, and title alignment.
- `impact_score`
  Based on source authority, recency, topic resonance, and content depth.
- `quality_score`
  Penalizes weak, shallow, clickbait-like, or low-information content.
- `discovery_score`
  Helps preserve high-value adjacent discoveries that are not an exact CV match.

### 5. Retention Strategy

An item can be retained for multiple reasons:

- it is strongly relevant to the CV
- it is a heavyweight industry event
- it is a strong discovery candidate with good quality and enough impact

This is intentionally broader than a strict relevance-only filter.

### 6. Optional AI Rerank

When `--ai-evaluate` is enabled:

1. local scoring performs wide recall
2. embeddings rerank the candidate pool semantically
3. the top subset is sent to the LLM for structured final judgment

This makes the system much more practical than either:

- local rules only
- full end-to-end LLM scoring on every document

## Key CLI Options

- `--resume`
  Path to the resume or CV file.
- `--sources`
  Source configuration file.
- `--per-source-limit`
  Number of recent entries to fetch per source.
- `--top-n`
  Number of ranked items to keep in the final report.
- `--min-relevance`
  Minimum relevance threshold for strong-fit retention.
- `--min-quality`
  Minimum quality threshold.
- `--heavyweight-impact`
  Impact threshold for preserving major industry events.
- `--ai-evaluate`
  Enables embedding rerank plus LLM refinement.
- `--ai-candidate-pool`
  Number of locally recalled items to send through embeddings.
- `--ai-top-k`
  Number of items to send to the LLM after embedding rerank.

## Suitable Use Cases

- track AI developments relevant to a specific engineering profile
- build a daily AI signal digest
- monitor frontier labs and platform vendors
- surface engineering-relevant content from broad research and media feeds
- support job search, research scanning, or competitive technical monitoring

## Notes for Public Repositories

Do not commit personal runtime artifacts such as:

- private `sources.json`
- local reports
- personal resumes
- cookies or authenticated source configs

The included `.gitignore` already excludes the common local-only files.
