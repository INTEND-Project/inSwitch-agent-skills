#!/usr/bin/env python3
"""Seed synthetic trace data into the local trace SQLite store.

Examples:
  python scripts/seed_traces.py
  python scripts/seed_traces.py --count 200 --window-hours 72
  TRACES_DB_PATH=./logs/traces.db python scripts/seed_traces.py --count 100
"""

import argparse
import json
import os
import random
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Dict, List


SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    span_id         TEXT PRIMARY KEY,
    trace_id        TEXT NOT NULL,
    parent_span_id  TEXT,
    name            TEXT NOT NULL,
    start_ts        REAL NOT NULL,
    end_ts          REAL,
    duration_ms     INTEGER,
    status          TEXT,
    attributes_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_spans_trace  ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_span_id);
CREATE INDEX IF NOT EXISTS idx_spans_start  ON spans(start_ts);
CREATE INDEX IF NOT EXISTS idx_spans_name   ON spans(name);
"""

INTENTS: List[str] = [
    "Find and rank top remote roles for senior backend engineers",
    "Analyze API latency spikes and suggest mitigation steps",
    "Plan a low-risk rollout strategy for a feature flag",
    "Summarize customer support tickets and extract recurring issues",
    "Create a weekly KPI report with action items for operations",
    "Compare cloud cost optimization options for this quarter",
    "Draft an incident postmortem outline from recent logs",
    "Generate a prioritized backlog from stakeholder notes",
]


def _default_db_path() -> str:
    env_path = os.getenv("TRACES_DB_PATH")
    if env_path:
        return env_path
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "logs" / "traces.db")


def _clip_duration_ms(value: float) -> int:
    return int(max(500, min(300_000, round(value))))


def _insert_span(
    conn: sqlite3.Connection,
    *,
    span_id: str,
    trace_id: str,
    parent_span_id: str,
    name: str,
    start_ts: float,
    duration_ms: int,
    status: str,
    attrs: Dict[str, object],
) -> None:
    end_ts = start_ts + (duration_ms / 1000.0)
    conn.execute(
        "INSERT INTO spans "
        "(span_id, trace_id, parent_span_id, name, start_ts, end_ts, duration_ms, status, attributes_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            span_id,
            trace_id,
            parent_span_id,
            name,
            start_ts,
            end_ts,
            duration_ms,
            status,
            json.dumps(attrs, ensure_ascii=True),
        ),
    )


def seed_traces(db_path: str, count: int, window_hours: int) -> None:
    now = time.time()
    window_seconds = max(1, window_hours) * 3600
    since_ts = now - window_seconds

    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_file))
    try:
        conn.executescript(SCHEMA)

        min_start = None
        max_start = None

        for i in range(count):
            trace_id = uuid.uuid4().hex
            root_span_id = uuid.uuid4().hex

            start_ts = random.uniform(since_ts, now)
            duration_ms = _clip_duration_ms(
                random.lognormvariate(mu=10.3, sigma=0.8)
            )
            total_cost_usd = round(random.uniform(0.001, 0.05), 6)
            status = "ok" if random.random() < 0.95 else "error"
            intent_text = INTENTS[i % len(INTENTS)]

            _insert_span(
                conn,
                span_id=root_span_id,
                trace_id=trace_id,
                parent_span_id=None,
                name="agent.request",
                start_ts=start_ts,
                duration_ms=duration_ms,
                status=status,
                attrs={"intent.text": intent_text},
            )

            llm_span_id = uuid.uuid4().hex
            llm_start = start_ts + random.uniform(0.02, min(2.0, duration_ms / 1000.0))
            llm_duration_ms = _clip_duration_ms(max(500, duration_ms * random.uniform(0.2, 0.9)))
            input_tokens = random.randint(150, 3000)
            output_tokens = random.randint(40, 1200)
            _insert_span(
                conn,
                span_id=llm_span_id,
                trace_id=trace_id,
                parent_span_id=root_span_id,
                name="gen_ai.chat",
                start_ts=llm_start,
                duration_ms=llm_duration_ms,
                status="ok",
                attrs={
                    "gen_ai.usage.cost_usd": total_cost_usd,
                    "gen_ai.usage.input_tokens": input_tokens,
                    "gen_ai.usage.output_tokens": output_tokens,
                    "model": random.choice(["gpt-5-mini", "gpt-5", "gpt-4o-mini"]),
                },
            )

            if min_start is None or start_ts < min_start:
                min_start = start_ts
            if max_start is None or start_ts > max_start:
                max_start = start_ts

        conn.commit()

        if count == 0:
            print(f"Inserted 0 traces into {db_file}")
            return

        print(f"Inserted {count} traces into {db_file}")
        print(
            "Trace start_ts range: "
            f"{int(min_start)} ({time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(min_start))}) "
            "-> "
            f"{int(max_start)} ({time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(max_start))})"
        )
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic traces into the tracing SQLite DB")
    parser.add_argument("--count", type=int, default=50, help="Number of traces to insert (default: 50)")
    parser.add_argument(
        "--window-hours",
        type=int,
        default=24,
        help="Distribute traces uniformly over the last H hours (default: 24)",
    )
    parser.add_argument(
        "--db-path",
        default=_default_db_path(),
        help="Path to trace DB (default: TRACES_DB_PATH or ./logs/traces.db)",
    )
    args = parser.parse_args()

    if args.count < 0:
        raise SystemExit("--count must be >= 0")
    if args.window_hours <= 0:
        raise SystemExit("--window-hours must be > 0")

    seed_traces(db_path=args.db_path, count=args.count, window_hours=args.window_hours)


if __name__ == "__main__":
    main()
