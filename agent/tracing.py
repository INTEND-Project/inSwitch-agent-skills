"""
Native tracing module for the fill-agent multi-agent system.

Zero external dependencies — everything runs on Python's standard library.
Captures a trace per user request, with spans for each agent turn, LLM call,
and tool invocation. Spans form a parent-child tree that naturally crosses
sub-agent boundaries via contextvars.

Design follows the trace/span model used by every industrial tracing system

Attribute names mirror the OTel GenAI
semantic conventions so that if we ever want to plug in a real backend
later, it's a trivial exporter and not a rewrite.

Public API:
    init_db()                 -> create the SQLite schema
    start_trace(name, attrs)  -> context manager, use at the top of each request
    start_span(name, attrs)   -> context manager, use for any inner operation
    compute_llm_cost(model, usage) -> float in USD
"""

import contextvars
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.getenv("TRACES_DB_PATH", "/logs/traces.db")

# Pricing per 1M tokens. Adjust to current OpenAI pricing when needed.
# Source: https://openai.com/api/pricing/
PRICING: Dict[str, Dict[str, float]] = {
    "gpt-5-mini":    {"input": 0.25,  "cached_input": 0.025, "output": 2.00},
    "gpt-5":         {"input": 1.25,  "cached_input": 0.125, "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15,  "cached_input": 0.075, "output": 0.60},
    "gpt-4o":        {"input": 2.50,  "cached_input": 1.25,  "output": 10.00},
}


# ---------------------------------------------------------------------------
# Context propagation
# ---------------------------------------------------------------------------
# The current span and trace are held in contextvars. Any code path that runs
# inside a `start_span` block — including sub-agent delegations — will see
# the correct parent. No explicit passing needed.

_current_span: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_span", default=None
)
_current_trace: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_trace", default=None
)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_SCHEMA = """
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


def init_db() -> None:
    """Create the spans table and indexes if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _insert_span(
    span_id: str,
    trace_id: str,
    parent_span_id: Optional[str],
    name: str,
    start_ts: float,
    end_ts: float,
    duration_ms: int,
    status: str,
    attributes: Dict[str, Any],
) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO spans "
            "(span_id, trace_id, parent_span_id, name, start_ts, end_ts, "
            " duration_ms, status, attributes_json) "
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
                json.dumps(attributes, default=str, ensure_ascii=True),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public context managers
# ---------------------------------------------------------------------------

class _SpanHandle:
    """Handle returned by start_span / start_trace.

    Use `.set(key, value)` or `.update({...})` to add attributes during
    the span's lifetime. Use `.mark_error(msg)` to record a non-exception
    failure (e.g., the tool returned an error dict rather than raising).
    """

    __slots__ = ("attrs", "status")

    def __init__(self, attrs: Dict[str, Any]):
        self.attrs: Dict[str, Any] = attrs
        self.status: str = "ok"

    def set(self, key: str, value: Any) -> None:
        self.attrs[key] = value

    def update(self, extra: Dict[str, Any]) -> None:
        self.attrs.update(extra)

    def mark_error(self, message: str) -> None:
        self.status = "error"
        self.attrs["error.message"] = message


@contextmanager
def start_trace(
    name: str, attrs: Optional[Dict[str, Any]] = None
) -> Iterator[_SpanHandle]:
    """Start a new trace. Use this once per user request (at the HTTP entry).

    Creates a fresh trace_id and a root span. Nested start_span calls will
    attach as children automatically.
    """
    trace_id = uuid.uuid4().hex
    trace_token = _current_trace.set(trace_id)
    try:
        with start_span(name, attrs) as handle:
            yield handle
    finally:
        _current_trace.reset(trace_token)


@contextmanager
def start_span(
    name: str, attrs: Optional[Dict[str, Any]] = None
) -> Iterator[_SpanHandle]:
    """Start a span inside the current trace.

    If no trace is active, starts a new implicit trace. Parent is taken from
    the current contextvar, so sub-agent delegations automatically nest
    correctly — no explicit parent passing required.
    """
    span_id = uuid.uuid4().hex
    parent_span_id = _current_span.get()
    trace_id = _current_trace.get()

    # Implicit trace fallback (e.g., span started outside an HTTP request)
    implicit_trace = False
    if trace_id is None:
        trace_id = uuid.uuid4().hex
        trace_token = _current_trace.set(trace_id)
        implicit_trace = True

    span_token = _current_span.set(span_id)
    handle = _SpanHandle(dict(attrs or {}))

    start_perf = time.perf_counter()
    start_ts = time.time()

    try:
        yield handle
    except Exception as exc:
        handle.mark_error(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        end_ts = time.time()
        duration_ms = int((time.perf_counter() - start_perf) * 1000)
        try:
            _insert_span(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=name,
                start_ts=start_ts,
                end_ts=end_ts,
                duration_ms=duration_ms,
                status=handle.status,
                attributes=handle.attrs,
            )
        except Exception:
            # Tracing must never break the main flow. Swallow storage errors.
            pass
        _current_span.reset(span_token)
        if implicit_trace:
            _current_trace.reset(trace_token)


# ---------------------------------------------------------------------------
# Cost helper
# ---------------------------------------------------------------------------

def compute_llm_cost(model: str, usage: Any) -> float:
    """Compute USD cost from an OpenAI response.usage object.

    Handles cached tokens if present. Returns 0.0 if the model isn't in
    the pricing table (logs nothing — caller can decide whether to warn).
    """
    prices = PRICING.get(model)
    if prices is None:
        return 0.0

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0

    # cached_tokens may live on usage or on usage.input_tokens_details
    cached = getattr(usage, "cached_tokens", None)
    if cached is None:
        details = getattr(usage, "input_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0)
    cached = cached or 0

    non_cached = max(input_tokens - cached, 0)

    return (
        non_cached * prices["input"] / 1_000_000
        + cached * prices["cached_input"] / 1_000_000
        + output_tokens * prices["output"] / 1_000_000
    )