import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { listTraces, TraceListItem } from '../../api/tracing';
import usePolledFetch from '../../hooks/usePolledFetch';

type TracesListViewProps = {
  onOpenTrace: (traceId: string) => void;
};

type SortKey =
  | 'start_ts'
  | 'intent_text'
  | 'duration_ms'
  | 'total_cost_usd'
  | 'llm_calls'
  | 'tool_calls'
  | 'status';

type SortDirection = 'asc' | 'desc';

const CACHE_TTL_MS = 10_000;
let tracesCache: { data: TraceListItem[]; fetchedAt: number } | null = null;

const formatStartTime = (unixSeconds: number) => {
  const date = new Date(unixSeconds * 1000);
  const hhmmss = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date);
  const ymd = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(
    date.getDate()
  ).padStart(2, '0')}`;
  return `${hhmmss} ${ymd}`;
};

const formatDuration = (durationMs: number) => {
  if (durationMs > 1000) {
    return `${(durationMs / 1000).toFixed(1)}s`;
  }
  return `${Math.round(durationMs)}ms`;
};

const formatCost = (cost: number) => `$${cost.toFixed(4)}`;

const truncateIntent = (intent: string, max = 50) => {
  if (intent.length <= max) return intent;
  return `${intent.slice(0, max - 1)}…`;
};

const formatUpdatedAt = (timestampMs: number) =>
  new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(new Date(timestampMs));

const compareTraces = (a: TraceListItem, b: TraceListItem, key: SortKey): number => {
  if (key === 'intent_text') return a.intent_text.localeCompare(b.intent_text);
  if (key === 'status') return a.status.localeCompare(b.status);

  const aValue = a[key as Exclude<SortKey, 'intent_text' | 'status'>] as number;
  const bValue = b[key as Exclude<SortKey, 'intent_text' | 'status'>] as number;
  return aValue - bValue;
};

const TracesListView: React.FC<TracesListViewProps> = ({ onOpenTrace }) => {
  const [traces, setTraces] = useState<TraceListItem[]>(tracesCache?.data ?? []);
  const [isLoading, setIsLoading] = useState(!tracesCache);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('start_ts');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(tracesCache?.fetchedAt ?? null);

  const loadTraces = useCallback(async (force = false) => {
    const hasFreshCache = !force && tracesCache && Date.now() - tracesCache.fetchedAt < CACHE_TTL_MS;

    if (hasFreshCache && tracesCache) {
      setTraces(tracesCache.data);
      setUpdatedAtMs(tracesCache.fetchedAt);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const result = await listTraces(50, 0);
      const fetchedAt = Date.now();
      tracesCache = { data: result.traces, fetchedAt };
      setTraces(result.traces);
      setUpdatedAtMs(fetchedAt);
    } catch (err) {
      console.error(err);
      setError('Unable to load traces. Check API host configuration and backend availability.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const { runNow } = usePolledFetch(() => loadTraces(false), 15_000);

  useEffect(() => {
    void runNow();
  }, [runNow]);

  const sortedTraces = useMemo(() => {
    const next = [...traces];
    next.sort((a, b) => {
      const base = compareTraces(a, b, sortKey);
      return sortDirection === 'asc' ? base : -base;
    });
    return next;
  }, [traces, sortDirection, sortKey]);

  const handleSort = (nextKey: SortKey) => {
    if (sortKey === nextKey) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(nextKey);
    setSortDirection('asc');
  };

  const sortArrow = (key: SortKey) => {
    if (sortKey !== key) return '↕';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  return (
    <div className="observability-summary">
      <div className="observability-summary-header">
        <div className="observability-header-title-wrap">
          <h3>Traces</h3>
          {updatedAtMs !== null && (
            <span className="observability-updated-at">
              Updated {formatUpdatedAt(updatedAtMs)}
            </span>
          )}
        </div>
        <button
          type="button"
          className="observability-action"
          onClick={() => void runNow(() => loadTraces(true))}
          disabled={isLoading}
          title="Force refresh"
          aria-label="Force refresh"
        >
          {isLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {isLoading && <p className="observability-inline-message">Loading traces…</p>}
      {!isLoading && error && <p className="observability-inline-error">{error}</p>}

      {!isLoading && !error && (
        <section className="tool-table-section">
          <table className="tool-table traces-table">
            <thead>
              <tr>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('start_ts')}>
                    Start time {sortArrow('start_ts')}
                  </button>
                </th>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('intent_text')}>
                    Intent {sortArrow('intent_text')}
                  </button>
                </th>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('duration_ms')}>
                    Duration {sortArrow('duration_ms')}
                  </button>
                </th>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('total_cost_usd')}>
                    Cost {sortArrow('total_cost_usd')}
                  </button>
                </th>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('llm_calls')}>
                    LLM calls {sortArrow('llm_calls')}
                  </button>
                </th>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('tool_calls')}>
                    Tool calls {sortArrow('tool_calls')}
                  </button>
                </th>
                <th>
                  <button type="button" className="sort-button" onClick={() => handleSort('status')}>
                    Status {sortArrow('status')}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedTraces.length === 0 ? (
                <tr>
                  <td colSpan={7} className="tool-table-empty">
                    No traces found.
                  </td>
                </tr>
              ) : (
                sortedTraces.map((trace) => (
                  <tr
                    key={trace.trace_id}
                    className={`traces-row ${
                      trace.status === 'error' ? 'traces-row-error' : ''
                    } ${trace.total_cost_usd > 0.01 ? 'traces-row-warning' : ''}`}
                    onClick={() => onOpenTrace(trace.trace_id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onOpenTrace(trace.trace_id);
                      }
                    }}
                  >
                    <td>{formatStartTime(trace.start_ts)}</td>
                    <td title={trace.intent_text}>{truncateIntent(trace.intent_text)}</td>
                    <td>{formatDuration(trace.duration_ms)}</td>
                    <td>{formatCost(trace.total_cost_usd)}</td>
                    <td>{trace.llm_calls}</td>
                    <td>{trace.tool_calls}</td>
                    <td>
                      <span className="status-cell">
                        <span className={`status-dot-small ${trace.status === 'ok' ? 'ok' : 'error'}`} />
                        {trace.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
};

export default TracesListView;
