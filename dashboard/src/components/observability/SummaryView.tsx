import React, { useCallback, useEffect, useState } from 'react';
import { getMetricsSummary, MetricsSummaryResponse } from '../../api/tracing';
import usePolledFetch from '../../hooks/usePolledFetch';
import { useCurrency } from '../../hooks/useCurrency';
import { formatCurrency } from '../../utils/currency';

type SummaryViewProps = {
  onOpenTraces: () => void;
};

const CACHE_TTL_MS = 10_000;
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

const SummaryView: React.FC<SummaryViewProps> = ({ onOpenTraces }) => {
  const { currency, rates } = useCurrency();
  const [data, setData] = useState<MetricsSummaryResponse | null>(summaryCache?.data ?? null);
  const [isLoading, setIsLoading] = useState(!summaryCache);
  const [error, setError] = useState<string | null>(null);
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(summaryCache?.fetchedAt ?? null);

  const loadSummary = useCallback(async (force = false) => {
    const hasFreshCache =
      !force && summaryCache && Date.now() - summaryCache.fetchedAt < CACHE_TTL_MS;

    if (hasFreshCache && summaryCache) {
      setData(summaryCache.data);
      setUpdatedAtMs(summaryCache.fetchedAt);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const result = await getMetricsSummary();
      const fetchedAt = Date.now();
      summaryCache = { data: result, fetchedAt };
      setData(result);
      setUpdatedAtMs(fetchedAt);
    } catch (err) {
      console.error(err);
      setError('Unable to load summary metrics. Check API host configuration and backend availability.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const { runNow } = usePolledFetch(() => loadSummary(false), 15_000);

  useEffect(() => {
    void runNow();
  }, [runNow]);

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
          onClick={() => void runNow(() => loadSummary(true))}
          disabled={isLoading}
          title="Force refresh"
          aria-label="Force refresh"
        >
          {isLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {isLoading && <p className="observability-inline-message">Loading summary metrics…</p>}
      {!isLoading && error && <p className="observability-inline-error">{error}</p>}

      {!isLoading && !error && data && (
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
