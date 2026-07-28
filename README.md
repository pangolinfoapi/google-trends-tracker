# Google Trends Tracker — Free & Open Source

[![Track](https://github.com/pangolinfoapi/google-trends-tracker/actions/workflows/track.yml/badge.svg)](https://github.com/pangolinfoapi/google-trends-tracker/actions/workflows/track.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![Built with Pangolinfo](https://img.shields.io/badge/built%20with-Pangolinfo-blue)](https://www.pangolinfo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Free & open-source Google Trends monitor.** Track keyword interest over time, get
> daily snapshots, spot rising and falling trends — powered by the
> [Pangolinfo SERP / Google Trends API](https://www.pangolinfo.com/serp-api/).

Part of the [Pangolinfo open-source ecosystem](related-projects.md). A tiny Python tool
(zero dependencies) that watches a list of keywords and records their Google Trends
relative-interest score (0–100) every day with GitHub Actions. Perfect for **SEO
research**, **content planning**, **product trend monitoring**, and **keyword trend
monitoring** without paying for an enterprise tool.

---

## Table of contents

- [Why](#why)
- [Features](#features)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Configuration](#configuration-keywordsjson)
- [How it works](#how-it-works)
- [🌐 Pangolinfo ecosystem](#-pangolinfo-ecosystem)
- [FAQ](#faq)
- [Roadmap](#roadmap)

---

## Why

- 🔎 **Google Trends API in Python** — no browser automation, no scraping. One call
  returns the full interest-over-time timeline.
- 📈 **Daily automated snapshots** — GitHub Actions runs every day and commits the
  latest values, so your repo becomes a living trend dataset.
- ▲▼ **Rising / falling detection** — each run computes the delta vs the previous
  point and flags direction.
- 🧩 **Sparklines** — the Markdown report renders a 14-day ASCII sparkline per keyword.
- 🆓 **Free tier** — 200 free API calls at
  [tool.pangolinfo.com](https://tool.pangolinfo.com). No credit card to start.

---

## Features

- 🌍 **Multi-region / multi-language** — track `US`, `GB`, `DE`… in `en-US`, `en-GB`…
- 📊 **Interest-over-time** — relative score 0–100 stored per day
- ▲▼ **Direction flags** — rising / falling / flat vs the previous snapshot
- 📉 **Sparklines** — 14-day ASCII trend in `reports/latest.md`
- 🗄️ **SQLite history** — query trends over any window
- 🤖 **Free daily automation** — GitHub Actions commits the report every day
- 🧩 **Zero dependencies** — Python standard library only

---

## Architecture

```
        ┌─────────────────────────────────────────────┐
        │  google-trends-tracker (this repo)           │
        │  google_trends_tracker.py · SQLite           │
        └───────────────────┬─────────────────────────┘
                            │  streamable-HTTP (MCP)
                            │  tools/call → keyword_trends
                            ▼
        ┌─────────────────────────────────────────────┐
        │   Pangolinfo MCP server                       │
        │   mcp.pangolinfo.com/mcp  (Bearer JWT)        │
        └───────────────────┬─────────────────────────┘
                            │  proxy → Google Trends
                            ▼
              Google Trends interest timeline (JSON)
```

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/pangolinfoapi/google-trends-tracker.git
cd google-trends-tracker

# 2. Add your free API key (no secrets in the repo — it's an env var)
export PANGOLIN_TOKEN="your-free-key-from-tool.pangolinfo.com"

# 3. (optional) edit keywords.json to track the keywords you care about
# 4. Run
python google_trends_tracker.py run
python google_trends_tracker.py report
```

The bundled `keywords.json` already tracks a few demo keywords so the tool works out of
the box — replace them with your own.

---

## Commands

| Command | What it does |
|---|---|
| `python google_trends_tracker.py init` | Create `keywords.json` from the example file |
| `python google_trends_tracker.py run` | Fetch trends for every keyword group and store snapshots |
| `python google_trends_tracker.py history` | Print tracked keywords and their latest values |
| `python google_trends_tracker.py report` | Generate `reports/latest.md` with deltas + sparklines |

---

## Configuration (`keywords.json`)

```json
[
  {
    "label": "kitchen",
    "keywords": ["air fryer", "rice cooker"],
    "region": "US",
    "time_range": "today 3-m",
    "language": "en-US"
  }
]
```

- `keywords` *(list[str], required)* — keywords to compare.
- `region` *(str)* — e.g. `US`, `GB`. Default `US`.
- `time_range` *(str)* — e.g. `today 1-m`, `today 3-m`, `today 12-m`. Default `today 12-m`.
- `language` *(str)* — e.g. `en-US`, `en-GB`. Default `en-US`.

---

## How it works

The script talks to the **Pangolinfo MCP endpoint** (`mcp.pangolinfo.com/mcp`) over
streamable HTTP — the same Model Context Protocol server AI assistants use — and calls
the `keyword_trends` tool. Responses are parsed defensively and stored in a local SQLite
database (`data/trends.db`). Everything is **Python standard library only**; there is
nothing to `pip install`.

> Prefer no code? Connect Claude / Cursor / Windsurf / ChatGPT to
> `https://mcp.pangolinfo.com/mcp` and call `keyword_trends` directly.

Full setup + automation guide: [docs/SETUP.md](docs/SETUP.md).

---

## 🌐 Pangolinfo ecosystem

### 🛰️ More free tools by [@pangolinfoapi](https://github.com/pangolinfoapi)

🏠 **Hub:** [All tools, landing pages & tutorials](https://pangolinfoapi.github.io/)

- [amazon-keyword-rank-tracker](https://pangolinfoapi.github.io/amazon-keyword-rank-tracker/) —
  track your Amazon keyword rankings daily
- [amazon-niche-finder](https://pangolinfoapi.github.io/amazon-niche-finder/) —
  discover low-competition Amazon niches
- [amazon-review-analyzer](https://pangolinfoapi.github.io/amazon-review-analyzer/) —
  Amazon review sentiment + complaint/praise theme mining

### 🏗️ Built on the official Pangolinfo projects ([by @Pangolin-spg](https://github.com/Pangolin-spg))

- [amazon-walmart-shopify-scrape-api](https://github.com/Pangolin-spg/amazon-walmart-shopify-scrape-api)
  ⭐ 56 — the underlying Scrape / SERP API (Google Trends via the SERP API)
- [openclaw-skill-pangolinfo](https://github.com/Pangolin-spg/openclaw-skill-pangolinfo)
  ⭐ 8 — real-time web scraper skill for OpenClaw & AI agents (Google SERP + AI Overviews)
- [openclaw-skills](https://github.com/Pangolin-spg/openclaw-skills)
  ⭐ 3 — OpenClaw skills: AI SERP + Amazon Scraper
- [pangolinfo-amazon-scraper](https://github.com/Pangolin-spg/pangolinfo-amazon-scraper)
  — official Python SDK for the Pangolinfo Scrape API

> Full map of official Pangolinfo projects, skills and the live MCP endpoint:
> [related-projects.md](related-projects.md).

---

## FAQ

**Do I need a Google account or the Google Trends UI?** No. Trends are fetched via the
Pangolinfo SERP/Google Trends API — one call returns the full timeline.

**Is my API key safe?** Yes — it is an env var locally and an encrypted Actions secret
on GitHub, never committed.

**How many keywords can I track for free?** 200 free calls; one `run` makes ~1 call per
keyword group in `keywords.json`.

**Is the score comparable across keywords?** Google Trends scores are relative *within*
the requested keyword set and time window (0–100), ideal for comparing co-tracked terms.

---

## Roadmap

- [ ] Multi-keyword comparison charts
- [ ] "Related queries" capture (rising / top)
- [ ] Alert on breakout (sudden spike)
- [ ] Geo map (interest by region)

---

## Contributing

Ideas and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Ecosystem map:
[related-projects.md](related-projects.md).

## License

MIT © 2026 pangolinfo
