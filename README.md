# Google Trends Tracker

> **Free & open-source Google Trends monitor.** Track keyword interest over time,
> get daily snapshots, spot rising and falling trends — powered by the
> [Pangolinfo SERP / Google Trends API](https://www.pangolinfo.com/serp-api/).

A tiny Python tool (zero dependencies) that watches a list of keywords and records
their Google Trends relative-interest score (0–100) every day with GitHub Actions.
The result is a public, version-controlled trend history you can link to, fork, or
build on. Perfect for **SEO research**, **content planning**, **product trend
monitoring**, and **keyword trend monitoring** without paying for an enterprise tool.

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

The bundled `keywords.json` already tracks a few demo keywords so the tool works
out of the box — replace them with your own.

## Commands

| Command | What it does |
|---|---|
| `python google_trends_tracker.py init` | Create `keywords.json` from the example file |
| `python google_trends_tracker.py run` | Fetch trends for every keyword group and store snapshots |
| `python google_trends_tracker.py history` | Print tracked keywords and their latest values |
| `python google_trends_tracker.py report` | Generate `reports/latest.md` with deltas + sparklines |

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

## How it works

The script talks to the **Pangolinfo MCP endpoint** (`mcp.pangolinfo.com/mcp`) over
streamable HTTP — the same Model Context Protocol server AI assistants use — and
calls the `keyword_trends` tool. Responses are parsed defensively and stored in a
local SQLite database (`data/trends.db`). Everything is **Python standard library
only**; there is nothing to `pip install`.

## Related open-source tools by pangolinfo

- [amazon-keyword-rank-tracker](https://github.com/pangolinfoapi/amazon-keyword-rank-tracker) — track your Amazon keyword rankings daily
- [amazon-niche-finder](https://github.com/pangolinfoapi/amazon-niche-finder) — discover low-competition Amazon niches

All powered by [Pangolinfo](https://www.pangolinfo.com) — get a free API key at
[tool.pangolinfo.com](https://tool.pangolinfo.com).

## License

MIT © 2026 pangolinfo
