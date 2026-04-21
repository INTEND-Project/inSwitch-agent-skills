import React, { useCallback, useEffect, useMemo, useState } from 'react';
import SummaryView from './SummaryView';
import TracesListView from './TracesListView';
import TraceDetailView from './TraceDetailView';
import { Currency, CURRENCIES } from '../../utils/currency';
import { CurrencyProvider, useCurrency } from '../../hooks/useCurrency';
import './observability.css';

type ObservabilitySubView = 'summary' | 'list' | 'detail';

type ObservabilityRoute = {
  subView: ObservabilitySubView;
  traceId: string | null;
  path: string;
};

type ObservabilityViewProps = {
  onPathChange?: (path: string) => void;
};

const normalizeTraceId = (raw: string | undefined) => {
  if (!raw) return null;
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
};

const parseRoute = (pathname: string): ObservabilityRoute => {
  const detailMatch = pathname.match(/^\/observability\/traces\/([^/]+)$/);
  if (detailMatch) {
    const traceId = normalizeTraceId(detailMatch[1]);
    return {
      subView: traceId ? 'detail' : 'list',
      traceId,
      path: traceId ? `/observability/traces/${encodeURIComponent(traceId)}` : '/observability/traces'
    };
  }

  if (pathname === '/observability/traces' || pathname === '/observability/traces/') {
    return { subView: 'list', traceId: null, path: '/observability/traces' };
  }

  return { subView: 'summary', traceId: null, path: '/observability' };
};

const ObservabilityViewContent: React.FC<ObservabilityViewProps> = ({ onPathChange }) => {
  const { currency, setCurrency, ratesAvailable } = useCurrency();
  const [route, setRoute] = useState<ObservabilityRoute>(() => parseRoute(window.location.pathname));

  const syncWithLocation = useCallback(() => {
    const nextRoute = parseRoute(window.location.pathname);
    setRoute(nextRoute);
    onPathChange?.(nextRoute.path);
  }, [onPathChange]);

  useEffect(() => {
    syncWithLocation();
  }, [syncWithLocation]);

  useEffect(() => {
    window.addEventListener('popstate', syncWithLocation);
    return () => {
      window.removeEventListener('popstate', syncWithLocation);
    };
  }, [syncWithLocation]);

  const navigateTo = useCallback(
    (path: string) => {
      if (window.location.pathname !== path) {
        window.history.pushState({}, '', path);
      }
      const nextRoute = parseRoute(path);
      setRoute(nextRoute);
      onPathChange?.(nextRoute.path);
    },
    [onPathChange]
  );

  const openSummary = useCallback(() => navigateTo('/observability'), [navigateTo]);
  const openTraces = useCallback(() => navigateTo('/observability/traces'), [navigateTo]);

  const openDetail = useCallback(
    (traceId: string) => {
      navigateTo(`/observability/traces/${encodeURIComponent(traceId)}`);
    },
    [navigateTo]
  );

  const detailPath = useMemo(() => {
    if (!route.traceId) return null;
    return `/observability/traces/${encodeURIComponent(route.traceId)}`;
  }, [route.traceId]);

  return (
    <main className="observability-shell">
      <section className="panel observability-panel">
        <div className="panel-header">
          <div>
            <p className="panel-title">Observability</p>
            <p className="panel-subtitle">Summary, trace list, and trace detail views.</p>
          </div>
        </div>

        <div className="observability-tabs" role="tablist" aria-label="Observability views">
          <button
            type="button"
            role="tab"
            className={`observability-tab ${route.subView === 'summary' ? 'active' : ''}`}
            aria-selected={route.subView === 'summary'}
            onClick={openSummary}
          >
            Summary
          </button>
          <button
            type="button"
            role="tab"
            className={`observability-tab ${route.subView === 'list' ? 'active' : ''}`}
            aria-selected={route.subView === 'list'}
            onClick={openTraces}
          >
            Traces
          </button>
          <button
            type="button"
            role="tab"
            className={`observability-tab ${route.subView === 'detail' ? 'active' : ''}`}
            aria-selected={route.subView === 'detail'}
            onClick={() => {
              if (detailPath) navigateTo(detailPath);
            }}
            disabled={!detailPath}
          >
            Detail
          </button>
          <select
            className="currency-selector"
            value={currency}
            onChange={(event) => setCurrency(event.target.value as Currency)}
            title={!ratesAvailable ? 'Exchange rates unavailable' : undefined}
            aria-label="Currency"
          >
            {CURRENCIES.map((entry) => (
              <option
                key={entry.code}
                value={entry.code}
                disabled={entry.code !== 'USD' && !ratesAvailable}
              >
                {entry.code}
              </option>
            ))}
          </select>
        </div>

        <div className="observability-content">
          {route.subView === 'summary' && <SummaryView onOpenTraces={openTraces} />}
          {route.subView === 'list' && <TracesListView onOpenTrace={openDetail} />}
          {route.subView === 'detail' && (
            <TraceDetailView traceId={route.traceId} onBackToTraces={openTraces} />
          )}
        </div>
      </section>
    </main>
  );
};

const ObservabilityView: React.FC<ObservabilityViewProps> = ({ onPathChange }) => (
  <CurrencyProvider>
    <ObservabilityViewContent onPathChange={onPathChange} />
  </CurrencyProvider>
);

export default ObservabilityView;
