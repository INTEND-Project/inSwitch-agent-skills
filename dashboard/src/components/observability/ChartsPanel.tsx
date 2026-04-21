import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import {
  getMetricsTimeseries,
  TimeseriesBucket,
  TimeseriesPoint,
  TimeseriesResponse,
  TimeseriesWindow
} from '../../api/tracing';
import usePolledFetch from '../../hooks/usePolledFetch';
import { useCurrency } from '../../hooks/useCurrency';
import { formatCurrency } from '../../utils/currency';

type ChartsPanelProps = {
  window: TimeseriesWindow;
};

type CachedTimeseries = {
  data: TimeseriesResponse;
  fetchedAt: number;
};

const CACHE_TTL_MS = 10_000;
const CHART_REFRESH_MS = 15_000;
const BRAND_CYAN = 'var(--brand-cyan, #14CAD4)';
const BRAND_MAGENTA = 'var(--brand-magenta, #FF5AFF)';

const timeseriesCache: Partial<Record<TimeseriesWindow, CachedTimeseries>> = {};

const formatBucketLabel = (timestampSec: number, bucket: TimeseriesBucket) => {
  const date = new Date(timestampSec * 1000);
  if (bucket === 'day') {
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: '2-digit'
    }).format(date);
  }
  const hour = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    hour12: false
  }).format(date);
  return `${hour}:00`;
};

const formatTooltipLabel = (timestampSec: number, bucket: TimeseriesBucket) =>
  new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: bucket === 'hour' ? '2-digit' : undefined,
    minute: bucket === 'hour' ? '2-digit' : undefined,
    hour12: false
  }).format(new Date(timestampSec * 1000));

const formatDurationTick = (value: number) => {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} s`;
  }
  return `${Math.round(value)} ms`;
};

const ChartsPanel: React.FC<ChartsPanelProps> = ({ window }) => {
  const { currency, rates } = useCurrency();
  const cached = timeseriesCache[window];
  const [data, setData] = useState<TimeseriesResponse | null>(cached?.data ?? null);
  const [isInitialLoading, setIsInitialLoading] = useState(!cached);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasDataRef = useRef(!!cached);

  const loadTimeseries = useCallback(
    async (options?: { force?: boolean; hardReload?: boolean }) => {
      const force = options?.force ?? false;
      const hardReload = options?.hardReload ?? false;
      const cachedEntry = timeseriesCache[window];
      const hasFreshCache =
        !force && cachedEntry && Date.now() - cachedEntry.fetchedAt < CACHE_TTL_MS;
      if (hasFreshCache && cachedEntry) {
        setData((prev) => (prev === cachedEntry.data ? prev : cachedEntry.data));
        setError((prev) => (prev === null ? prev : null));
        setIsInitialLoading(false);
        setIsRefreshing(false);
        hasDataRef.current = true;
        return;
      }

      const hasExistingData = hasDataRef.current || !!timeseriesCache[window];
      if (hardReload) {
        setData(null);
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
        const result = await getMetricsTimeseries({ window });
        const fetchedAt = Date.now();
        timeseriesCache[window] = { data: result, fetchedAt };
        setData(result);
        setError((prev) => (prev === null ? prev : null));
        hasDataRef.current = true;
      } catch (err) {
        console.error(err);
        setError('Unable to load timeseries metrics. Check backend availability.');
      } finally {
        setIsInitialLoading(false);
        setIsRefreshing(false);
      }
    },
    [window]
  );

  const { runNow } = usePolledFetch(() => loadTimeseries(), CHART_REFRESH_MS);

  useEffect(() => {
    const cacheEntry = timeseriesCache[window];
    if (cacheEntry) {
      hasDataRef.current = true;
      setData((prev) => (prev === cacheEntry.data ? prev : cacheEntry.data));
      setError((prev) => (prev === null ? prev : null));
      setIsInitialLoading(false);
    } else {
      hasDataRef.current = false;
      setData((prev) => (prev === null ? prev : null));
      setIsInitialLoading(true);
    }
    setIsRefreshing(false);
    void runNow();
  }, [runNow, window]);

  const chartData = useMemo(() => {
    if (!data) return [];
    return data.points.map((point) => ({
      ...point,
      label: formatBucketLabel(point.bucket_start_ts, data.bucket),
      tooltipLabel: formatTooltipLabel(point.bucket_start_ts, data.bucket)
    }));
  }, [data]);

  if (isInitialLoading && !data) {
    return <p className="observability-inline-message">Loading chart metrics…</p>;
  }

  if (!isInitialLoading && !data && error) {
    return <p className="observability-inline-error">{error}</p>;
  }

  if (!data) return null;

  return (
    <div className="observability-charts-panel">
      {isRefreshing && (
        <span className="observability-refresh-indicator" aria-label="Refreshing" title="Refreshing" />
      )}
      {error && <p className="observability-inline-error">Showing previous data. {error}</p>}
      <section className="observability-charts-grid" aria-label="Timeseries charts">
        <article className="observability-chart-card">
        <h4>Traces per bucket</h4>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.35)" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip
              labelFormatter={(_, payload) =>
                formatTooltipLabel(
                  (payload?.[0]?.payload as TimeseriesPoint | undefined)?.bucket_start_ts ?? 0,
                  data.bucket
                )
              }
            />
            <Bar dataKey="trace_count" fill={BRAND_CYAN} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
        </article>

        <article className="observability-chart-card">
        <h4>Cost per bucket</h4>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.35)" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatCurrency(Number(value), currency, rates)} />
            <Tooltip
              formatter={(value) => [formatCurrency(Number(value), currency, rates), 'Cost']}
              labelFormatter={(_, payload) =>
                formatTooltipLabel(
                  (payload?.[0]?.payload as TimeseriesPoint | undefined)?.bucket_start_ts ?? 0,
                  data.bucket
                )
              }
            />
            <Line type="monotone" dataKey="total_cost_usd" stroke={BRAND_MAGENTA} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        </article>

        <article className="observability-chart-card">
        <h4>Latency (avg vs p95)</h4>
        <div className="observability-chart-legend" aria-hidden="true">
          <span className="legend-item">
            <span className="legend-dot legend-dot-cyan" />
            Avg
          </span>
          <span className="legend-item">
            <span className="legend-dot legend-dot-magenta" />
            P95
          </span>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.35)" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(value) => formatDurationTick(Number(value))} />
            <Tooltip
              formatter={(value, name) => [
                value == null ? 'N/A' : formatDurationTick(Number(value)),
                name === 'avg_duration_ms' ? 'Avg' : 'P95'
              ]}
              labelFormatter={(_, payload) =>
                formatTooltipLabel(
                  (payload?.[0]?.payload as TimeseriesPoint | undefined)?.bucket_start_ts ?? 0,
                  data.bucket
                )
              }
            />
            <Line
              type="monotone"
              dataKey="avg_duration_ms"
              stroke={BRAND_CYAN}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="p95_duration_ms"
              stroke={BRAND_MAGENTA}
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
        </article>

        <article className="observability-chart-card">
        <h4>Success vs error</h4>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.35)" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip
              labelFormatter={(_, payload) =>
                formatTooltipLabel(
                  (payload?.[0]?.payload as TimeseriesPoint | undefined)?.bucket_start_ts ?? 0,
                  data.bucket
                )
              }
            />
            <Bar dataKey="success_count" stackId="status" fill="#22c55e" isAnimationActive={false} />
            <Bar dataKey="error_count" stackId="status" fill="#ef4444" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
        </article>
      </section>
    </div>
  );
};

export default ChartsPanel;
