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
- Optional OpenAI-compatible rerank:
  - embedding-based semantic rerank
  - LLM-based final structured judgment
  - raw HTTP requests to OpenAI-compatible endpoints for enterprise gateways
  - graceful degradation across `full`, `chat-only`, `local-only`, and `failed-fallback`
- Offline report viewer for local JSON visualization
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
├── viewer
│   ├── app.js
│   ├── index.html
│   └── styles.css
└── src/ai_hotspot_monitor
    ├── api.py
    ├── cli.py
    ├── config.py
    ├── fetcher.py
    ├── models.py
    ├── pipeline.py
    ├── resume.py
    └── scoring.py
```

## Quick Start

macOS / Linux:

```bash
cd /Users/sheldonzhao/Desktop/github/signalrank-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp sources.curated.json sources.json
```

Windows PowerShell:

```powershell
Set-Location "D:/github/signalrank-ai"
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item sources.curated.json sources.json
```

Run a local-only pass:

```bash
ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json
```

Run the interactive web UI:

```bash
cd /Users/sheldonzhao/Desktop/github/signalrank-ai
signalrank-web
```

By default it starts at [http://127.0.0.1:8000](http://127.0.0.1:8000). You can override the bind address with:

```bash
cd /Users/sheldonzhao/Desktop/github/signalrank-ai
SIGNALRANK_HOST=127.0.0.1 SIGNALRANK_PORT=8765 signalrank-web
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

Run with a direct API key argument:

```bash
ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json \
  --ai-evaluate \
  --openai-api-key your_key \
  --embedding-model text-embedding-3-small \
  --ai-model gpt-5-mini
```

Run with an OpenAI-compatible company gateway:

```bash
export OPENAI_API_KEY="your_key"

ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json \
  --ai-evaluate \
  --openai-api-key your_chat_key \
  --openai-base-url http://your-company-gateway/v1 \
  --generation-api chat-completions \
  --ai-model qwen3.5 \
  --embedding-model your-embedding-model \
  --embedding-api-key your_embedding_key \
  --embedding-base-url http://your-embedding-gateway/v1
```

If the embedding endpoint is unavailable or returns an error, the pipeline automatically falls back to `chat-only` refinement instead of exiting.

Set explicit request timeouts when needed:

```bash
ai-hotspot-monitor \
  --resume ./path/to/resume.md \
  --sources ./sources.json \
  --ai-evaluate \
  --chat-timeout 300 \
  --embedding-timeout 60
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
- layered resume profile output:
  - `resume_focus_terms`
  - `resume_stack_terms`
  - `resume_background_terms`
  - `excluded_resume_terms`
- matched resume terms
- local scores
- final scores
- optional embedding score
- refinement mode: `disabled`, `chat-only`, `full`, `local-only`, or `failed-fallback`
- degrade metadata:
  - `ai_error`
  - `degrade_reason`
  - `ai_refined_count`
  - `ai_override_count`
  - `degraded_count`
  - `source_failed_count`
- keep decision and keep reason
- explanation fields:
  - `relevance_channel`
  - `significance_type`
  - `decision_source`
  - `keep_reason_category`
- retention class such as `resume-fit`, `industry-heavyweight`, `demo-potential`, or `interview-material`
- heavyweight-event flag

## How It Works

### 1. Resume Profiling

The resume is normalized and converted into a layered profile:

- `resume_focus_terms`
- `resume_stack_terms`
- `resume_background_terms`
- `excluded_resume_terms`
- a short focus summary

Section headers, generic education terms, and weak platform names are separated instead of being mixed into the main relevance signal.

### 2. Collection and Cleanup

Configured feeds are fetched, parsed, and cleaned.
The crawler attempts to extract article bodies while degrading gracefully when pages return `403`, `404`, or weak HTML.

### 3. Deduplication and Topic Grouping

The pipeline removes duplicate URLs and groups similar titles into topic clusters.
This helps avoid overweighting the same story across multiple sources.

### 4. Local Scoring

Each item is scored across multiple dimensions:

- `relevance_score`
  Direct resume relevance using TF-IDF similarity, layered term overlap, and title alignment.
- `ecosystem_significance`
  Technical ecosystem spillover across infra, runtime, tooling, model ecosystem, and hardware categories.
- `impact_score`
  Based on source authority, recency, topic resonance, and content depth.
- `quality_score`
  Penalizes weak, shallow, clickbait-like, or low-information content.
- `discovery_score`
  Helps preserve high-value adjacent discoveries that are not an exact CV match.

### 5. Retention Strategy

An item can be retained through two channels:

- `direct_resume_match`
- `ecosystem_shift`

Heavyweight logic is also split:

- `technical_ecosystem_heavyweight`
- `corporate_or_consumer_heavyweight`

This keeps the system focused on personalized engineering signal instead of devolving into either simple keyword matching or generic big-tech news aggregation.

### 6. Optional AI Rerank

When `--ai-evaluate` is enabled:

1. local scoring performs wide recall
2. embeddings rerank the candidate pool semantically when available
3. the top subset is sent to the LLM for structured final judgment

The runtime uses raw HTTP requests, not the OpenAI SDK. That makes enterprise gateway behavior more observable and easier to debug.

If embeddings are unavailable, the pipeline degrades to `chat-only`.
If some chat evaluations fail, those items keep their local ranking.
If AI refinement fails globally, the pipeline still writes JSON and Markdown using local results.

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
- `--ai-expand-resume`
  Adds an optional second expansion layer that uses the chat model to expand resume focus terms. If it fails, the pipeline falls back to rule-based expansion.
- `--ai-candidate-pool`
  Number of locally recalled items to send through embeddings.
- `--chat-timeout`
  Timeout in seconds for chat generation requests.
- `--embedding-timeout`
  Timeout in seconds for embedding requests.

## Offline Viewer

The repository includes a lightweight offline viewer for local JSON reports:

```bash
open ./viewer/index.html
```

Or open [`viewer/index.html`](./viewer/index.html) directly in a browser.

The page supports:

- top-level report overview
- result list with keep/discard status
- filters for keep status, relevance channel, significance type, AI refined, and source
- detail panel with scores, local scores, metadata, and AI override visibility
- English / Chinese toggle

## Interactive Web UI

The same viewer can also run in interactive mode when served by the backend API.

In this mode, the page can:

- upload a resume file
- choose a sources preset or upload a sources JSON file
- configure AI flags, models, base URLs, API keys, and timeouts
- trigger the pipeline through `POST /api/run`
- render the returned report immediately

The backend still does the real work:

- feed collection
- article cleanup
- local scoring
- embedding rerank
- AI refinement
- report file persistence under `./reports_web`

The browser does not call model endpoints directly.
- `--ai-top-k`
  Number of items to send to the LLM after embedding rerank.
- `--embedding-api-key`
  Direct API key for the embedding endpoint.
- `--embedding-api-key-env`
  Environment variable for the embedding API key.
- `--embedding-base-url`
  Optional OpenAI-compatible base URL for the embedding endpoint.
- `--generation-api`
  Choose `responses` or `chat-completions` for the AI rerank stage. Use `chat-completions` for gateways that do not support `/v1/responses`.
- `--openai-api-key`
  Direct API key input for the chat/generation endpoint. Overrides the environment-variable lookup.
- `--openai-base-url`
  Optional OpenAI-compatible base URL. Useful for company-hosted gateways, proxies, or compatible deployments.

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
