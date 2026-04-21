import React, { useCallback, useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { prism } from "react-syntax-highlighter/dist/esm/styles/prism";
import { getTrace, TraceSpan } from "../../api/tracing";
import { useCurrency } from "../../hooks/useCurrency";
import { formatCurrency } from "../../utils/currency";

type TraceDetailViewProps = {
  traceId: string | null;
  onBackToTraces: () => void;
};

type WaterfallSpan = TraceSpan & {
  depth: number;
  leftPct: number;
  widthPct: number;
};

type TraceStats = {
  totalDurationMs: number;
  totalCostUsd: number;
  llmCallCount: number;
  toolCallCount: number;
};

type TraceCacheEntry = {
  spans: WaterfallSpan[];
  rawSpans: TraceSpan[];
  stats: TraceStats;
  fetchedAt: number;
};

const CACHE_TTL_MS = 10_000;
const traceCache = new Map<string, TraceCacheEntry>();

const formatDuration = (durationMs: number) => {
  if (durationMs > 1000) return `${(durationMs / 1000).toFixed(1)}s`;
  return `${Math.round(durationMs)}ms`;
};

const getBarToneClass = (name: string, status: "ok" | "error") => {
  if (name.startsWith("gen_ai."))
    return status === "error" ? "bar-gen-ai-error" : "bar-gen-ai";
  if (name.startsWith("tool."))
    return status === "error" ? "bar-tool-error" : "bar-tool";
  return status === "error" ? "bar-agent-error" : "bar-agent";
};

const readNumber = (value: unknown) => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const extractCost = (attributes: Record<string, unknown>) => {
  const keys = [
    "gen_ai.usage.cost_usd",
    "gen_ai.cost_usd",
    "cost_usd",
    "total_cost_usd",
    "usage.cost_usd",
  ];
  for (const key of keys) {
    const parsed = readNumber(attributes[key]);
    if (parsed !== null) return parsed;
  }
  return 0;
};

const buildStats = (sorted: TraceSpan[]): TraceStats => {
  if (sorted.length === 0) {
    return {
      totalDurationMs: 0,
      totalCostUsd: 0,
      llmCallCount: 0,
      toolCallCount: 0,
    };
  }

  const traceStart = sorted[0].start_ts;
  const traceEnd = sorted.reduce(
    (max, span) => Math.max(max, span.end_ts),
    traceStart,
  );
  const totalDurationMs = Math.max((traceEnd - traceStart) * 1000, 0);

  let totalCostUsd = 0;
  let llmCallCount = 0;
  let toolCallCount = 0;

  for (const span of sorted) {
    if (span.name.startsWith("gen_ai.")) llmCallCount += 1;
    if (span.name.startsWith("tool.")) toolCallCount += 1;
    totalCostUsd += extractCost(span.attributes);
  }

  return { totalDurationMs, totalCostUsd, llmCallCount, toolCallCount };
};

const buildRulerMarks = (totalDurationMs: number) => {
  const points = [0, 0.25, 0.5, 0.75, 1];
  return points.map((point) => ({
    positionPct: point * 100,
    label: `${Math.round(totalDurationMs * point)}ms`,
  }));
};

const renderAttributes = (attributes: Record<string, unknown>) => {
  const entries = Object.entries(attributes);
  if (entries.length === 0) {
    return <p className="span-attributes-empty">No attributes</p>;
  }

  return (
    <div className="span-attributes-grid">
      {entries.map(([key, value]) => (
        <div key={key} className="span-attribute-row">
          <span className="span-attribute-key">{key}</span>
          <span className="span-attribute-value">
            {typeof value === "string" ? value : JSON.stringify(value)}
          </span>
        </div>
      ))}
    </div>
  );
};

const formatUpdatedAt = (timestampMs: number) =>
  new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestampMs));

const TraceDetailView: React.FC<TraceDetailViewProps> = ({
  traceId,
  onBackToTraces,
}) => {
  const { currency, rates } = useCurrency();
  const [spans, setSpans] = useState<WaterfallSpan[]>([]);
  const [rawSpans, setRawSpans] = useState<TraceSpan[]>([]);
  const [stats, setStats] = useState<TraceStats>({
    totalDurationMs: 0,
    totalCostUsd: 0,
    llmCallCount: 0,
    toolCallCount: 0,
  });
  const [expandedSpanId, setExpandedSpanId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(null);

  const loadTrace = useCallback(
    async (force = false) => {
      if (!traceId) {
        setSpans([]);
        setRawSpans([]);
        setExpandedSpanId(null);
        setError(null);
        setUpdatedAtMs(null);
        setStats({
          totalDurationMs: 0,
          totalCostUsd: 0,
          llmCallCount: 0,
          toolCallCount: 0,
        });
        return;
      }

      const cached = traceCache.get(traceId);
      const hasFreshCache =
        !force && cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS;

      if (hasFreshCache && cached) {
        setSpans(cached.spans);
        setRawSpans(cached.rawSpans);
        setStats(cached.stats);
        setUpdatedAtMs(cached.fetchedAt);
        setError(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        const result = await getTrace(traceId);
        const sorted = [...result.spans].sort(
          (a, b) => a.start_ts - b.start_ts,
        );
        const byId = new Map(sorted.map((span) => [span.span_id, span]));

        const traceStart = sorted.length > 0 ? sorted[0].start_ts : 0;
        const traceEnd = sorted.reduce(
          (max, span) => Math.max(max, span.end_ts),
          traceStart,
        );
        const totalSeconds = Math.max(traceEnd - traceStart, 0.001);

        const withGeometry: WaterfallSpan[] = sorted.map((span) => {
          let depth = 0;
          let parentId = span.parent_span_id;
          const seen = new Set<string>();
          while (parentId && !seen.has(parentId)) {
            seen.add(parentId);
            depth += 1;
            const parent = byId.get(parentId);
            if (!parent) break;
            parentId = parent.parent_span_id;
          }

          const leftPct = ((span.start_ts - traceStart) / totalSeconds) * 100;
          const durationSec = Math.max(span.duration_ms / 1000, 0.001);
          const widthPct = (durationSec / totalSeconds) * 100;

          return {
            ...span,
            depth,
            leftPct,
            widthPct,
          };
        });

        const computedStats = buildStats(sorted);
        const fetchedAt = Date.now();

        traceCache.set(traceId, {
          spans: withGeometry,
          rawSpans: sorted,
          stats: computedStats,
          fetchedAt,
        });
        setRawSpans(sorted);
        setSpans(withGeometry);
        setStats(computedStats);
        setUpdatedAtMs(fetchedAt);
      } catch (err) {
        console.error(err);
        setError(
          "Unable to load trace detail. Check API host configuration and backend availability.",
        );
        setSpans([]);
        setRawSpans([]);
        setStats({
          totalDurationMs: 0,
          totalCostUsd: 0,
          llmCallCount: 0,
          toolCallCount: 0,
        });
      } finally {
        setIsLoading(false);
      }
    },
    [traceId],
  );

  useEffect(() => {
    setShowRaw(false);
    setExpandedSpanId(null);
    void loadTrace(false);
  }, [loadTrace]);

  if (!traceId) {
    return (
      <div className="observability-placeholder">
        <h3>Trace Detail</h3>
        <p>Select a trace from the list to view its waterfall.</p>
      </div>
    );
  }

  const rulerMarks = buildRulerMarks(stats.totalDurationMs);

  return (
    <div className="observability-summary">
      <div className="observability-summary-header">
        <div className="detail-header-left">
          <button
            type="button"
            className="detail-back-link"
            onClick={onBackToTraces}
          >
            Back to traces
          </button>
          <h3>Trace Detail</h3>
          {updatedAtMs !== null && (
            <span className="observability-updated-at">
              Updated {formatUpdatedAt(updatedAtMs)}
            </span>
          )}
        </div>
        <button
          type="button"
          className="observability-action"
          onClick={() => void loadTrace(true)}
          disabled={isLoading}
          title="Force refresh"
          aria-label="Force refresh"
        >
          {isLoading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <p className="observability-inline-message">Trace ID: {traceId}</p>
      {isLoading && (
        <p className="observability-inline-message">Loading trace spans…</p>
      )}
      {!isLoading && error && (
        <p className="observability-inline-error">{error}</p>
      )}

      {!isLoading && !error && (
        <>
          <section className="trace-summary-bar">
            <article className="trace-summary-item">
              <span className="trace-summary-label">Total duration</span>
              <span className="trace-summary-value">
                {formatDuration(stats.totalDurationMs)}
              </span>
            </article>
            <article className="trace-summary-item">
              <span className="trace-summary-label">Total cost</span>
              <span className="trace-summary-value">
                {formatCurrency(stats.totalCostUsd, currency, rates)}
              </span>
            </article>
            <article className="trace-summary-item">
              <span className="trace-summary-label">LLM calls</span>
              <span className="trace-summary-value">{stats.llmCallCount}</span>
            </article>
            <article className="trace-summary-item">
              <span className="trace-summary-label">Tool calls</span>
              <span className="trace-summary-value">{stats.toolCallCount}</span>
            </article>
          </section>

          <section className="waterfall-section">
            {spans.length === 0 ? (
              <p className="observability-inline-message">
                No spans found for this trace.
              </p>
            ) : (
              <>
                <div className="waterfall-ruler">
                  <div className="waterfall-ruler-label-cell" />
                  <div className="waterfall-ruler-track">
                    {rulerMarks.map((mark, index) => (
                      <div
                        key={mark.positionPct}
                        className={`waterfall-ruler-mark ${
                          index === 0
                            ? "is-start"
                            : index === rulerMarks.length - 1
                              ? "is-end"
                              : ""
                        }`}
                        style={{ left: `${mark.positionPct}%` }}
                      >
                        <span className="waterfall-ruler-tick" />
                        <span className="waterfall-ruler-label">
                          {mark.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="waterfall-list">
                  {spans.map((span) => {
                    const isExpanded = expandedSpanId === span.span_id;
                    return (
                      <div key={span.span_id} className="waterfall-span-wrap">
                        <div className="waterfall-row">
                          <div
                            className="waterfall-label"
                            style={{ paddingLeft: `${span.depth * 12}px` }}
                          >
                            <span className="waterfall-name">{span.name}</span>
                            <span className="waterfall-duration">
                              {formatDuration(span.duration_ms)}
                            </span>
                            <button
                              type="button"
                              className="span-attributes-toggle"
                              onClick={() =>
                                setExpandedSpanId((prev) =>
                                  prev === span.span_id ? null : span.span_id,
                                )
                              }
                              aria-label={
                                isExpanded
                                  ? "Collapse span attributes"
                                  : "Expand span attributes"
                              }
                              aria-expanded={isExpanded}
                              aria-controls={`span-attributes-${span.span_id}`}
                            >
                              <span
                                className={`span-toggle-arrow ${isExpanded ? "is-expanded" : ""}`}
                                aria-hidden="true"
                              >
                                ▸
                              </span>
                            </button>
                          </div>
                          <div className="waterfall-track">
                            <div
                              className={`waterfall-bar ${getBarToneClass(span.name, span.status)}`}
                              style={{
                                left: `${Math.max(0, Math.min(span.leftPct, 100))}%`,
                                width: `${Math.max(Math.min(span.widthPct, 100), 0.35)}%`,
                              }}
                            />
                          </div>
                        </div>
                        {isExpanded && (
                          <div
                            className="span-attributes-panel"
                            id={`span-attributes-${span.span_id}`}
                          >
                            {renderAttributes(span.attributes)}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </section>
        </>
      )}

      {!isLoading && !error && (
        <details
          className="raw-spans"
          onToggle={(event) =>
            setShowRaw((event.target as HTMLDetailsElement).open)
          }
        >
          <summary>Raw spans</summary>
          {showRaw && (
            <div className="raw-spans-content">
              <SyntaxHighlighter
                PreTag="div"
                language="json"
                style={prism}
                wrapLongLines
                customStyle={{
                  margin: 0,
                  borderRadius: "0.75rem",
                  padding: "0.75rem 0.85rem",
                  background: "transparent",
                }}
              >
                {JSON.stringify(rawSpans, null, 2)}
              </SyntaxHighlighter>
            </div>
          )}
        </details>
      )}
    </div>
  );
};

export default TraceDetailView;
