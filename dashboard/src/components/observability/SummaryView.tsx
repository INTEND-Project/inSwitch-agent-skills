import React, { useCallback, useEffect, useRef, useState } from 'react';
import { getMetricsSummary, MetricsSummaryResponse, TimeseriesWindow } from '../../api/tracing';
import usePolledFetch from '../../hooks/usePolledFetch';
import { useCurrency } from '../../hooks/useCurrency';
import { formatCurrency } from '../../utils/currency';
import ChartsPanel from './ChartsPanel';

type SummaryViewProps = {
  onOpenTraces: () => void;
};

const CACHE_TTL_MS = 10_000;
const CHARTS_WINDOW_STORAGE_KEY = 'observability.chartsWindow';
const WINDOW_OPTIONS: TimeseriesWindow[] = ['24h', '7d', '30d'];
let summaryCache: { data: MetricsSummaryResponse; fetchedAt: number } | null = null;

const formatSuccessRate = (value: number) => `${(value * 100).toFixed(1)}%`;

const formatAvgDuration = (durationMs: number) => {
  if (durationMs > 1000) {
    return `${(durationMs / 1000).toFixed(2)} s`;
  }
  return `${Math.round(durationMs)} ms`;
};

const formatUpdatedAt = (timestampMs: number) =>
  new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(new Date(timestampMs));

const isTimeseriesWindow = (value: string): value is TimeseriesWindow =>
  WINDOW_OPTIONS.includes(value as TimeseriesWindow);

const SummaryView: React.FC<SummaryViewProps> = ({ onOpenTraces }) => {
  const { currency, rates } = useCurrency();
  const [data, setData] = useState<MetricsSummaryResponse | null>(summaryCache?.data ?? null);
  const [isInitialLoading, setIsInitialLoading] = useState(!summaryCache);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(summaryCache?.fetchedAt ?? null);
  const [chartsWindow, setChartsWindow] = useState<TimeseriesWindow>('24h');
  const hasDataRef = useRef(!!summaryCache);

  const loadSummary = useCallback(async (options?: { force?: boolean; hardReload?: boolean }) => {
    const force = options?.force ?? false;
    const hardReload = options?.hardReload ?? false;
    const hasFreshCache =
      !force && summaryCache && Date.now() - summaryCache.fetchedAt < CACHE_TTL_MS;

    if (hasFreshCache && summaryCache) {
      setData((prev) => (prev === summaryCache.data ? prev : summaryCache.data));
      setUpdatedAtMs(summaryCache.fetchedAt);
      setError((prev) => (prev === null ? prev : null));
      setIsInitialLoading(false);
      setIsRefreshing(false);
      hasDataRef.current = true;
      return;
    }

    const hasExistingData = hasDataRef.current || !!summaryCache;
    if (hardReload) {
      setData(null);
      setUpdatedAtMs(null);
      setIsInitialLoading(true);
      hasDataRef.current = false;
    } else if (!hasExistingData) {
      setIsInitialLoading(true);
    } else {
      setIsRefreshing(true);
    }
    if (!hasExistingData || hardReload) {
      setError((prev) => (prev === null ? prev : null));
    }

    try {
      const result = await getMetricsSummary();
      const fetchedAt = Date.now();
      summaryCache = { data: result, fetchedAt };
      setData(result);
      setUpdatedAtMs(fetchedAt);
      setError((prev) => (prev === null ? prev : null));
      hasDataRef.current = true;
    } catch (err) {
      console.error(err);
      setError('Unable to load summary metrics. Check API host configuration and backend availability.');
    } finally {
      setIsInitialLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  const { runNow } = usePolledFetch(() => loadSummary(), 15_000);

  useEffect(() => {
    void runNow();
  }, [runNow]);

  useEffect(() => {
    const stored = window.localStorage.getItem(CHARTS_WINDOW_STORAGE_KEY);
    if (stored && isTimeseriesWindow(stored)) {
      setChartsWindow(stored);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(CHARTS_WINDOW_STORAGE_KEY, chartsWindow);
  }, [chartsWindow]);

  return (
    <div className="observability-summary">
      <div className="observability-summary-header">
        <div className="observability-header-title-wrap">
          <h3>Summary</h3>
          {updatedAtMs !== null && (
            <span className="observability-updated-at">
              Updated {formatUpdatedAt(updatedAtMs)}
            </span>
          )}
        </div>
        <button
          type="button"
          className="observability-action"
          onClick={(event) =>
            void runNow(() => loadSummary({ force: true, hardReload: event.shiftKey }))
          }
          disabled={isInitialLoading || isRefreshing}
          title="Refresh (Shift+click for hard reload)"
          aria-label="Force refresh"
        >
          {isInitialLoading || isRefreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {isInitialLoading && !data && (
        <p className="observability-inline-message">Loading summary metrics…</p>
      )}
      {!isInitialLoading && !data && error && <p className="observability-inline-error">{error}</p>}
      {data && error && <p className="observability-inline-error">Showing previous data. {error}</p>}

      {data && (
        <>
          <div className="kpi-grid kpi-grid-main">
            <article className="kpi-card kpi-card-cost">
              <p className="kpi-label">Cost (24h)</p>
              <p className="kpi-value">{formatCurrency(data.total_cost_usd, currency, rates)}</p>
            </article>

            <button
              type="button"
              className="kpi-card kpi-card-button kpi-card-traces"
              onClick={onOpenTraces}
              title="Open traces list"
            >
              <p className="kpi-label">Traces (24h)</p>
              <p className="kpi-value">{data.trace_count}</p>
            </button>

            <article className="kpi-card kpi-card-success">
              <p className="kpi-label">Success rate (24h)</p>
              <p className="kpi-value">{formatSuccessRate(data.success_rate)}</p>
            </article>
          </div>

          <div className="kpi-grid kpi-grid-extra">
            <article className="kpi-card kpi-card-duration">
              <p className="kpi-label">Avg duration</p>
              <p className="kpi-value">{formatAvgDuration(data.avg_duration_ms)}</p>
            </article>
          </div>

          <div className="observability-charts-section">
            <div className="observability-charts-header">
              <h4>Activity over time</h4>
              <div className="timeseries-window-switch" role="group" aria-label="Timeseries window">
                {WINDOW_OPTIONS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`timeseries-window-button ${chartsWindow === option ? 'is-active' : ''}`}
                    onClick={() => setChartsWindow(option)}
                    aria-pressed={chartsWindow === option}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
            <ChartsPanel window={chartsWindow} />
          </div>

          <section className="tool-table-section summary-tools-section">
            <h4>Top tools</h4>
            <table className="tool-table summary-tools-table">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {data.top_tools.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="tool-table-empty">
                      No tool calls in this period.
                    </td>
                  </tr>
                ) : (
                  data.top_tools.map((row) => (
                    <tr key={row.tool}>
                      <td>{row.tool}</td>
                      <td>{row.count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
};

export default SummaryView;
