"""
Read-only HTTP endpoints that expose the tracing data to the dashboard.

Plug into the existing HTTP server in app.py by calling
    handle_trace_request(path, query, send_json)
from the `do_GET` method when the path starts with /traces or /metrics.

Three endpoints:
    GET /traces                    -> paginated list of recent traces
    GET /traces/{trace_id}         -> full span tree for one trace
    GET /metrics/summary           -> aggregates over a time window
"""

import json
import os
import sqlite3
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

DB_PATH = os.getenv("TRACES_DB_PATH", "/logs/traces.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_span(row: sqlite3.Row) -> Dict[str, Any]:
    attrs = {}
    if row["attributes_json"]:
        try:
            attrs = json.loads(row["attributes_json"])
        except json.JSONDecodeError:
            attrs = {}
    return {
        "span_id": row["span_id"],
        "trace_id": row["trace_id"],
        "parent_span_id": row["parent_span_id"],
        "name": row["name"],
        "start_ts": row["start_ts"],
        "end_ts": row["end_ts"],
        "duration_ms": row["duration_ms"],
        "status": row["status"],
        "attributes": attrs,
    }


# ---------------------------------------------------------------------------
# GET /traces  -> list of recent traces (one row per trace, summary info)
# ---------------------------------------------------------------------------

def list_traces(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Return a paginated list of traces with summary stats for each.

    A 'trace' is represented by its root span (parent_span_id IS NULL).
    Cost and LLM-call count are aggregated across all spans in the trace.
    """
    conn = _connect()
    try:
        roots = conn.execute(
            "SELECT span_id, trace_id, name, start_ts, duration_ms, status, "
            "       attributes_json "
            "FROM spans "
            "WHERE parent_span_id IS NULL "
            "ORDER BY start_ts DESC "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

        traces = []
        for root in roots:
            trace_id = root["trace_id"]
            agg = conn.execute(
                "SELECT "
                "  COUNT(*) AS span_count, "
                "  SUM(CASE WHEN name = 'gen_ai.chat' THEN 1 ELSE 0 END) "
                "    AS llm_calls, "
                "  SUM(CASE WHEN name = 'tool.call' THEN 1 ELSE 0 END) "
                "    AS tool_calls "
                "FROM spans WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()

            # Sum cost from attributes_json of gen_ai.chat spans
            cost_rows = conn.execute(
                "SELECT attributes_json FROM spans "
                "WHERE trace_id = ? AND name = 'gen_ai.chat'",
                (trace_id,),
            ).fetchall()
            total_cost = 0.0
            for cr in cost_rows:
                try:
                    a = json.loads(cr["attributes_json"] or "{}")
                    total_cost += float(a.get("gen_ai.usage.cost_usd", 0) or 0)
                except (json.JSONDecodeError, ValueError):
                    pass

            root_attrs = {}
            if root["attributes_json"]:
                try:
                    root_attrs = json.loads(root["attributes_json"])
                except json.JSONDecodeError:
                    pass

            traces.append({
                "trace_id": trace_id,
                "root_name": root["name"],
                "start_ts": root["start_ts"],
                "duration_ms": root["duration_ms"],
                "status": root["status"],
                "intent_text": root_attrs.get("intent.text", ""),
                "span_count": agg["span_count"],
                "llm_calls": agg["llm_calls"] or 0,
                "tool_calls": agg["tool_calls"] or 0,
                "total_cost_usd": round(total_cost, 6),
            })

        return {"traces": traces, "limit": limit, "offset": offset}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /traces/{trace_id}  -> full span tree for one trace
# ---------------------------------------------------------------------------

def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_ts ASC",
            (trace_id,),
        ).fetchall()
        if not rows:
            return None
        spans = [_row_to_span(r) for r in rows]
        return {"trace_id": trace_id, "spans": spans}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GET /metrics/summary  -> aggregates over a time window
# ---------------------------------------------------------------------------

def metrics_summary(since_ts: Optional[float] = None) -> Dict[str, Any]:
    """Aggregates since a given unix timestamp (default: last 24h)."""
    import time as _time
    if since_ts is None:
        since_ts = _time.time() - 24 * 3600

    conn = _connect()
    try:
        # Total cost and LLM call count
        cost_rows = conn.execute(
            "SELECT attributes_json FROM spans "
            "WHERE name = 'gen_ai.chat' AND start_ts >= ?",
            (since_ts,),
        ).fetchall()
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        for r in cost_rows:
            try:
                a = json.loads(r["attributes_json"] or "{}")
                total_cost += float(a.get("gen_ai.usage.cost_usd", 0) or 0)
                total_input_tokens += int(a.get("gen_ai.usage.input_tokens", 0) or 0)
                total_output_tokens += int(a.get("gen_ai.usage.output_tokens", 0) or 0)
            except (json.JSONDecodeError, ValueError):
                pass

        # Trace count
        trace_count = conn.execute(
            "SELECT COUNT(DISTINCT trace_id) AS c FROM spans "
            "WHERE start_ts >= ? AND parent_span_id IS NULL",
            (since_ts,),
        ).fetchone()["c"]

        # Success rate
        success_row = conn.execute(
            "SELECT "
            "  SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_count, "
            "  COUNT(*) AS total "
            "FROM spans WHERE parent_span_id IS NULL AND start_ts >= ?",
            (since_ts,),
        ).fetchone()
        success_rate = (
            success_row["ok_count"] / success_row["total"]
            if success_row["total"] else 0.0
        )

        # Average latency per root span
        avg_row = conn.execute(
            "SELECT AVG(duration_ms) AS avg_ms FROM spans "
            "WHERE parent_span_id IS NULL AND start_ts >= ?",
            (since_ts,),
        ).fetchone()

        # Top tool calls by count
        top_tools = conn.execute(
            "SELECT attributes_json FROM spans "
            "WHERE name = 'tool.call' AND start_ts >= ?",
            (since_ts,),
        ).fetchall()
        tool_counts: Dict[str, int] = {}
        for r in top_tools:
            try:
                a = json.loads(r["attributes_json"] or "{}")
                tname = a.get("tool.name", "unknown")
                tool_counts[tname] = tool_counts.get(tname, 0) + 1
            except json.JSONDecodeError:
                pass
        tool_ranking = sorted(
            tool_counts.items(), key=lambda kv: kv[1], reverse=True
        )

        return {
            "since_ts": since_ts,
            "trace_count": trace_count,
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "success_rate": round(success_rate, 4),
            "avg_duration_ms": int(avg_row["avg_ms"] or 0),
            "top_tools": [
                {"tool": t, "count": c} for t, c in tool_ranking[:10]
            ],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Request dispatcher — wire this into your existing do_GET
# ---------------------------------------------------------------------------

def handle_trace_request(
    path: str, send_json: Callable[[int, Dict[str, Any]], None]
) -> bool:
    """Dispatch /traces and /metrics/* requests.

    Returns True if the path was handled, False if it's not a tracing path
    (so the caller can fall through to other handlers).
    """
    parsed = urlparse(path)
    query = parse_qs(parsed.query)

    # GET /traces
    if parsed.path == "/traces":
        try:
            limit = int(query.get("limit", ["50"])[0])
            offset = int(query.get("offset", ["0"])[0])
        except ValueError:
            send_json(400, {"error": "Invalid limit/offset"})
            return True
        send_json(200, list_traces(limit=limit, offset=offset))
        return True

    # GET /traces/{trace_id}
    if parsed.path.startswith("/traces/"):
        trace_id = parsed.path[len("/traces/"):]
        if not trace_id:
            send_json(400, {"error": "Missing trace_id"})
            return True
        result = get_trace(trace_id)
        if result is None:
            send_json(404, {"error": "Trace not found"})
        else:
            send_json(200, result)
        return True

    # GET /metrics/summary
    if parsed.path == "/metrics/summary":
        since = query.get("since_ts", [None])[0]
        since_ts = float(since) if since else None
        send_json(200, metrics_summary(since_ts=since_ts))
        return True

    return False