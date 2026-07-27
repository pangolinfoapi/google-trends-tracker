#!/usr/bin/env python3
"""Google Trends Tracker — monitor keyword interest over time, free & open source.

Uses the Pangolinfo MCP endpoint (https://mcp.pangolinfo.com/mcp) — the same
Model Context Protocol server AI assistants use — to call ``keyword_trends``
against Google Trends, and stores daily snapshots in SQLite so you can watch
interest rise and fall for the keywords that matter to you.

Zero dependencies: Python 3.10+ standard library only.

Commands:
    init      Create keywords.json from the example file
    run       Fetch trends for every configured keyword group and store snapshots
    history   Print tracked keywords (optionally filtered by label)
    report    Generate a Markdown report with deltas and sparklines

Get a free API key (200 free calls) at https://tool.pangolinfo.com
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "keywords.json"
EXAMPLE_FILE = ROOT / "keywords.example.json"
DB_FILE = ROOT / "data" / "trends.db"
REPORTS_DIR = ROOT / "reports"

MCP_URL = os.environ.get("PANGOLIN_MCP_URL", "https://mcp.pangolinfo.com/mcp")
MCP_PROTOCOL_VERSION = "2024-11-05"

# The MCP endpoint sits behind Cloudflare, which blocks default library
# signatures (python-urllib gets Error 1010). Present a browser UA.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS trends (
  trend_key TEXT PRIMARY KEY,
  keyword TEXT NOT NULL,
  region TEXT NOT NULL,
  time_range TEXT NOT NULL,
  latest_value REAL,
  prev_value REAL,
  delta REAL,
  direction TEXT,
  avg_value REAL,
  peak_value REAL,
  peak_date TEXT,
  first_seen_at TEXT,
  last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS trend_history (
  trend_key TEXT NOT NULL,
  captured_date TEXT NOT NULL,
  value REAL,
  PRIMARY KEY (trend_key, captured_date)
);
"""


# --------------------------------------------------------------------------- #
# Minimal MCP (streamable-HTTP) client — stdlib only
# --------------------------------------------------------------------------- #

class McpError(RuntimeError):
    pass


class McpClient:
    """Talks JSON-RPC to the Pangolinfo MCP server over streamable-HTTP."""

    def __init__(self, token: str, url: str = MCP_URL, timeout: int = 90) -> None:
        self.token = token
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self._next_id = 0
        self._initialized = False

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Authorization", f"Bearer {self.token}")
        if self.session_id:
            req.add_header("mcp-session-id", self.session_id)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("mcp-session-id")
                if sid:
                    self.session_id = sid
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise McpError(f"HTTP {exc.code} from MCP server: {exc.read()[:200]!r}") from exc
        except urllib.error.URLError as exc:
            raise McpError(f"MCP server unreachable: {exc}") from exc
        if not raw.strip():
            return {}
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return json.loads(raw)

    def initialize(self) -> None:
        self._next_id += 1
        self._post({
            "jsonrpc": "2.0", "id": self._next_id, "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "google-trends-tracker", "version": "1.0.0"},
            },
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        self._initialized = True

    def call_tool(self, name: str, arguments: dict) -> dict:
        if not self._initialized:
            self.initialize()
        self._next_id += 1
        resp = self._post({
            "jsonrpc": "2.0", "id": self._next_id, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        if "error" in resp:
            raise McpError(f"JSON-RPC error: {resp['error']}")
        result = resp.get("result", {})
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        if result.get("isError"):
            raise McpError("tool error: " + (" ".join(texts)[:300] or "unknown"))
        for text in texts:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
        return {}


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #

def extract_trends_json(payload: dict) -> dict:
    """Pull the inner Google Trends ``json`` object out of a keyword_trends response."""
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("json"), dict):
        return payload["json"]
    if isinstance(payload.get("data"), dict):
        inner = payload["data"]
        if isinstance(inner.get("json"), dict):
            return inner["json"]
        return inner
    if "timelineData" in payload or "keywordsRankData" in payload or "geoMapData" in payload:
        return payload
    return {}


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def keyword_series(timeline_data: list, index: int) -> list:
    """Return [(formattedTime, value)] for keyword at position ``index``."""
    series = []
    for point in timeline_data or []:
        raw = point.get("value")
        v = None
        if isinstance(raw, list) and index < len(raw):
            v = safe_float(raw[index])
        series.append((point.get("formattedTime"), v, point.get("time")))
    return series


def analyze_series(series: list) -> dict:
    """Compute summary stats from a keyword's timeline series."""
    values = [(t, v) for (t, v, _ts) in series if v is not None]
    if not values:
        return {"latest": None, "prev": None, "delta": None, "direction": "n/a",
                "avg": None, "peak": None, "peak_date": None}
    latest_t, latest = values[-1]
    prev_t, prev = values[-2] if len(values) >= 2 else (None, None)
    delta = None if prev is None else round(latest - prev, 2)
    direction = "flat"
    if prev is not None and prev != 0:
        if latest > prev * 1.05:
            direction = "rising"
        elif latest < prev * 0.95:
            direction = "falling"
    vals = [v for _t, v in values]
    peak_t, peak = max(values, key=lambda x: x[1])
    return {
        "latest": latest,
        "prev": prev,
        "delta": delta,
        "direction": direction,
        "avg": round(sum(vals) / len(vals), 2),
        "peak": peak,
        "peak_date": peak_t,
    }


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #

def db_connect() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def upsert_trend(conn: sqlite3.Connection, row: dict, now: str) -> None:
    conn.execute(
        """INSERT INTO trends
           (trend_key, keyword, region, time_range, latest_value, prev_value,
            delta, direction, avg_value, peak_value, peak_date, first_seen_at, last_seen_at)
           VALUES (:trend_key, :keyword, :region, :time_range, :latest_value, :prev_value,
                   :delta, :direction, :avg_value, :peak_value, :peak_date, :first_seen_at, :last_seen_at)
           ON CONFLICT(trend_key) DO UPDATE SET
             latest_value=excluded.latest_value, prev_value=excluded.prev_value,
             delta=excluded.delta, direction=excluded.direction, avg_value=excluded.avg_value,
             peak_value=excluded.peak_value, peak_date=excluded.peak_date,
             last_seen_at=excluded.last_seen_at""",
        row,
    )
    conn.commit()


def append_history(conn: sqlite3.Connection, trend_key: str, date: str, value) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO trend_history (trend_key, captured_date, value)
           VALUES (?, ?, ?)""",
        (trend_key, date, value),
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Sparkline helper
# --------------------------------------------------------------------------- #

def sparkline(values: list, width: int = 14) -> str:
    if not values:
        return "·"
    nums = [v for v in values if v is not None]
    if not nums:
        return "·"
    lo, hi = min(nums), max(nums)
    ramp = "▁▂▃▄▅▆▇█"
    span = hi - lo
    out = []
    for v in values[-width:]:
        if v is None:
            out.append(" ")
        else:
            idx = 0 if span == 0 else int((v - lo) / span * (len(ramp) - 1))
            out.append(ramp[idx])
    return "".join(out)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_init() -> None:
    if CONFIG_FILE.exists():
        sys.exit("keywords.json already exists — edit it directly.")
    CONFIG_FILE.write_text(EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created {CONFIG_FILE.name} — add the keywords you want to track.")


def cmd_run(args) -> None:
    if not CONFIG_FILE.exists():
        sys.exit("keywords.json not found. Run: python google_trends_tracker.py init")
    groups = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    token = os.environ.get("PANGOLIN_TOKEN") or os.environ.get("PANGOLINFO_API_KEY")
    if not token:
        sys.exit("Set PANGOLIN_TOKEN env var (free key: https://tool.pangolinfo.com)")

    conn = db_connect()
    client = McpClient(token=token)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = datetime.now(timezone.utc).date().isoformat()
    processed, stored = 0, 0

    for group in groups:
        label = group.get("label", "group")
        keywords = group["keywords"]
        region = group.get("region", "US")
        time_range = group.get("time_range", "today 12-m")
        language = group.get("language", "en-US")
        arguments = {
            "keywords": keywords,
            "time_range": time_range,
            "region": region,
            "language": language,
        }
        processed += 1
        try:
            payload = client.call_tool("keyword_trends", arguments)
        except McpError as exc:
            print(f"  ! {label}: {exc}")
            time.sleep(args.delay)
            continue

        tj = extract_trends_json(payload)
        timeline = tj.get("timelineData", [])
        if not timeline:
            print(f"  · {label}: no timeline data returned")
            time.sleep(args.delay)
            continue

        for idx, kw in enumerate(keywords):
            series = keyword_series(timeline, idx)
            stats = analyze_series(series)
            trend_key = f"{kw}|{region}|{time_range}"
            row = {
                "trend_key": trend_key,
                "keyword": kw,
                "region": region,
                "time_range": time_range,
                "latest_value": stats["latest"],
                "prev_value": stats["prev"],
                "delta": stats["delta"],
                "direction": stats["direction"],
                "avg_value": stats["avg"],
                "peak_value": stats["peak"],
                "peak_date": stats["peak_date"],
                "first_seen_at": now,
                "last_seen_at": now,
            }
            upsert_trend(conn, row, now)
            append_history(conn, trend_key, today, stats["latest"])
            stored += 1
            arrow = {"rising": "▲", "falling": "▼", "flat": "▬", "n/a": "·"}.get(stats["direction"], "·")
            print(f"  {arrow} {kw[:32]:<32} latest={stats['latest']} "
                  f"delta={stats['delta']} ({stats['direction']})")
        time.sleep(args.delay)

    print(f"\nDone: stored {stored} keyword snapshots across {processed} groups. DB: {DB_FILE.relative_to(ROOT)}")


def cmd_history(args) -> None:
    conn = db_connect()
    query = "SELECT keyword, region, time_range, latest_value, delta, direction, last_seen_at FROM trends"
    params = []
    if args.label:
        query += " WHERE keyword LIKE ?"
        params.append(f"%{args.label}%")
    query += " ORDER BY latest_value DESC NULLS LAST LIMIT ?"
    params.append(args.limit)
    rows = conn.execute(query, params).fetchall()
    if not rows:
        print("No data yet. Run: python google_trends_tracker.py run")
        return
    print(f"{'keyword':<34}{'region':<6}{'latest':>7}{'delta':>8}  dir")
    print("-" * 64)
    for kw, region, tr, latest, delta, direction, seen in rows:
        arrow = {"rising": "▲", "falling": "▼", "flat": "▬", "n/a": "·"}.get(direction, "·")
        print(f"{kw[:33]:<34}{region:<6}{str(latest):>7}{str(delta):>8}  {arrow}")


def cmd_report(_args) -> None:
    conn = db_connect()
    REPORTS_DIR.mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()

    rows = conn.execute(
        """SELECT trend_key, keyword, region, time_range, latest_value, delta, direction
           FROM trends ORDER BY latest_value DESC NULLS LAST LIMIT 200"""
    ).fetchall()
    if not rows:
        print("No trends tracked yet. Run: python google_trends_tracker.py run")
        return

    lines = [
        f"# Google Trends Tracker — {today}",
        "",
        "Monitored with [google-trends-tracker](https://github.com/pangolinfoapi/google-trends-tracker) "
        "using the [Pangolinfo SERP / Google Trends API](https://www.pangolinfo.com/serp-api/).",
        "",
        "> Values are Google Trends relative interest (0–100). ▲ rising, ▼ falling, ▬ flat.",
        "",
        "## Keyword interest",
        "",
        "| Keyword | Region | Latest | Δ (vs prev point) | Trend | 14-day sparkline |",
        "|---|---|---|---|---|---|",
    ]
    for trend_key, kw, region, tr, latest, delta, direction in rows:
        hist = conn.execute(
            "SELECT value FROM trend_history WHERE trend_key = ? ORDER BY captured_date",
            (trend_key,),
        ).fetchall()
        vals = [r[0] for r in hist]
        arrow = {"rising": "▲", "falling": "▼", "flat": "▬", "n/a": "·"}.get(direction, "·")
        lines.append(
            f"| {kw} | {region} | {latest if latest is not None else '—'} | "
            f"{delta if delta is not None else '—'} | {arrow} | `{sparkline(vals)}` |"
        )

    report = "\n".join(lines) + "\n"
    (REPORTS_DIR / f"{today}.md").write_text(report, encoding="utf-8")
    (REPORTS_DIR / "latest.md").write_text(report, encoding="utf-8")
    print(f"Report written: reports/{today}.md, reports/latest.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Trends Tracker (powered by Pangolinfo)")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls (default: 2)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create keywords.json from the example")
    sub.add_parser("run", help="Fetch trends for all configured keyword groups")
    hist = sub.add_parser("history", help="Show tracked keywords")
    hist.add_argument("--label")
    hist.add_argument("--limit", type=int, default=50)
    sub.add_parser("report", help="Generate Markdown report with sparklines")

    args = parser.parse_args()
    {"init": cmd_init, "run": cmd_run, "history": cmd_history, "report": cmd_report}[args.command](args)


if __name__ == "__main__":
    main()
