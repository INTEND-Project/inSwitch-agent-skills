import json
import os
import sqlite3
import sys
import tempfile
import unittest


TEST_DIR = os.path.dirname(__file__)
AGENT_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

import trace_api


SCHEMA = """
CREATE TABLE spans (
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
"""


class MetricsTimeseriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "traces.db")
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

        self.old_db_path = trace_api.DB_PATH
        trace_api.DB_PATH = self.db_path

    def tearDown(self) -> None:
        trace_api.DB_PATH = self.old_db_path
        self.tmp.cleanup()

    def _insert_span(
        self,
        span_id: str,
        trace_id: str,
        name: str,
        start_ts: float,
        duration_ms: int,
        status: str = "ok",
        parent_span_id: str = None,
        attributes: dict = None,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
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
                    start_ts + (duration_ms / 1000.0),
                    duration_ms,
                    status,
                    json.dumps(attributes or {}, ensure_ascii=True),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_empty_store_returns_zero_filled_points(self) -> None:
        data = trace_api.metrics_timeseries(window="24h", bucket="hour", now_ts=1_700_000_000)
        self.assertEqual(data["window"], "24h")
        self.assertEqual(data["bucket"], "hour")
        self.assertEqual(len(data["points"]), 24)
        for point in data["points"]:
            self.assertEqual(point["trace_count"], 0)
            self.assertEqual(point["total_cost_usd"], 0.0)
            self.assertEqual(point["success_count"], 0)
            self.assertEqual(point["error_count"], 0)
            self.assertIsNone(point["avg_duration_ms"])
            self.assertIsNone(point["p95_duration_ms"])

    def test_fixture_traces_land_in_expected_buckets(self) -> None:
        now_ts = 1_700_000_000
        response = trace_api.metrics_timeseries(window="24h", bucket="hour", now_ts=now_ts)
        since_ts = response["since_ts"]

        first_bucket = since_ts + (5 * 3600)
        last_bucket = since_ts + (23 * 3600)

        self._insert_span("r1", "t1", "agent.request", first_bucket + 120, 100, status="ok")
        self._insert_span("r2", "t2", "agent.request", first_bucket + 2400, 300, status="error")
        self._insert_span("r3", "t3", "agent.request", last_bucket + 30, 500, status="ok")

        self._insert_span(
            "c1",
            "t1",
            "gen_ai.chat",
            first_bucket + 130,
            10,
            parent_span_id="r1",
            attributes={"gen_ai.usage.cost_usd": 0.1},
        )
        self._insert_span(
            "c2",
            "t2",
            "gen_ai.chat",
            first_bucket + 2500,
            10,
            parent_span_id="r2",
            attributes={"gen_ai.usage.cost_usd": 0.2},
        )
        self._insert_span(
            "c3",
            "t3",
            "gen_ai.chat",
            last_bucket + 60,
            10,
            parent_span_id="r3",
            attributes={"gen_ai.usage.cost_usd": 0.3},
        )

        data = trace_api.metrics_timeseries(window="24h", bucket="hour", now_ts=now_ts)
        points_by_start = {p["bucket_start_ts"]: p for p in data["points"]}

        bucket_a = points_by_start[first_bucket]
        self.assertEqual(bucket_a["trace_count"], 2)
        self.assertEqual(bucket_a["success_count"], 1)
        self.assertEqual(bucket_a["error_count"], 1)
        self.assertEqual(bucket_a["total_cost_usd"], 0.3)
        self.assertEqual(bucket_a["avg_duration_ms"], 200.0)
        self.assertEqual(bucket_a["p95_duration_ms"], 300.0)

        bucket_b = points_by_start[last_bucket]
        self.assertEqual(bucket_b["trace_count"], 1)
        self.assertEqual(bucket_b["success_count"], 1)
        self.assertEqual(bucket_b["error_count"], 0)
        self.assertEqual(bucket_b["total_cost_usd"], 0.3)
        self.assertEqual(bucket_b["avg_duration_ms"], 500.0)
        self.assertEqual(bucket_b["p95_duration_ms"], 500.0)

    def test_p95_is_null_for_empty_bucket(self) -> None:
        now_ts = 1_700_000_000
        data = trace_api.metrics_timeseries(window="7d", bucket="hour", now_ts=now_ts)
        self.assertEqual(len(data["points"]), 168)
        empty_bucket = data["points"][42]
        self.assertEqual(empty_bucket["trace_count"], 0)
        self.assertIsNone(empty_bucket["p95_duration_ms"])
        self.assertIsNone(empty_bucket["avg_duration_ms"])

    def test_includes_current_hour_bucket(self) -> None:
        now_ts = 1_700_000_000
        data = trace_api.metrics_timeseries(window="24h", bucket="hour", now_ts=now_ts)
        current_hour_start = int(now_ts // 3600) * 3600
        self.assertEqual(data["points"][-1]["bucket_start_ts"], current_hour_start)

        self._insert_span("r4", "t4", "agent.request", current_hour_start + 120, 250, status="ok")
        self._insert_span(
            "c4",
            "t4",
            "gen_ai.chat",
            current_hour_start + 180,
            20,
            parent_span_id="r4",
            attributes={"gen_ai.usage.cost_usd": 0.5},
        )

        refreshed = trace_api.metrics_timeseries(window="24h", bucket="hour", now_ts=now_ts)
        current_point = refreshed["points"][-1]
        self.assertEqual(current_point["bucket_start_ts"], current_hour_start)
        self.assertEqual(current_point["trace_count"], 1)
        self.assertEqual(current_point["success_count"], 1)
        self.assertEqual(current_point["error_count"], 0)
        self.assertEqual(current_point["avg_duration_ms"], 250.0)
        self.assertEqual(current_point["p95_duration_ms"], 250.0)
        self.assertEqual(current_point["total_cost_usd"], 0.5)


if __name__ == "__main__":
    unittest.main()
