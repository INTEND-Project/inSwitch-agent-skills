const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
export const API_BASE = configuredBase && configuredBase.length > 0
  ? configuredBase.replace(/\/+$/, '')
  : 'http://localhost:8085';

type TraceStatus = 'ok' | 'error';

export type TraceListItem = {
  trace_id: string;
  root_name: string;
  start_ts: number;
  duration_ms: number;
  status: TraceStatus;
  intent_text: string;
  span_count: number;
  llm_calls: number;
  tool_calls: number;
  total_cost_usd: number;
};

export type TracesResponse = {
  traces: TraceListItem[];
  limit: number;
  offset: number;
};

export type TraceSpan = {
  span_id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: 'agent.request' | 'agent.turn' | 'gen_ai.chat' | 'tool.call';
  start_ts: number;
  end_ts: number;
  duration_ms: number;
  status: TraceStatus;
  attributes: Record<string, unknown>;
};

export type TraceDetailResponse = {
  trace_id: string;
  spans: TraceSpan[];
};

export type TopTool = {
  tool: string;
  count: number;
};

export type MetricsSummaryResponse = {
  since_ts: number;
  trace_count: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  success_rate: number;
  avg_duration_ms: number;
  top_tools: TopTool[];
};

export type TimeseriesWindow = '24h' | '7d' | '30d';
export type TimeseriesBucket = 'hour' | 'day';

export type TimeseriesPoint = {
  bucket_start_ts: number;
  trace_count: number;
  total_cost_usd: number;
  avg_duration_ms: number | null;
  p95_duration_ms: number | null;
  success_count: number;
  error_count: number;
};

export type TimeseriesResponse = {
  window: TimeseriesWindow;
  bucket: TimeseriesBucket;
  since_ts: number;
  until_ts: number;
  points: TimeseriesPoint[];
};

const assertOk = async (response: Response) => {
  if (response.ok) return;
  throw new Error(`Request failed (${response.status})`);
};

const apiUrl = (path: string) => `${API_BASE}${path}`;

export const fetchTraces = async (params?: {
  limit?: number;
  offset?: number;
}): Promise<TracesResponse> => {
  const search = new URLSearchParams();
  if (typeof params?.limit === 'number') search.set('limit', String(params.limit));
  if (typeof params?.offset === 'number') search.set('offset', String(params.offset));

  const query = search.toString();
  const url = `${apiUrl('/traces')}${query ? `?${query}` : ''}`;
  const response = await fetch(url);
  await assertOk(response);
  return (await response.json()) as TracesResponse;
};

export const fetchTraceDetail = async (traceId: string): Promise<TraceDetailResponse> => {
  const response = await fetch(apiUrl(`/traces/${encodeURIComponent(traceId)}`));
  await assertOk(response);
  return (await response.json()) as TraceDetailResponse;
};

export const fetchMetricsSummary = async (): Promise<MetricsSummaryResponse> => {
  const response = await fetch(apiUrl('/metrics/summary'));
  await assertOk(response);
  return (await response.json()) as MetricsSummaryResponse;
};

export const fetchMetricsTimeseries = async (params?: {
  window?: TimeseriesWindow;
  bucket?: TimeseriesBucket;
}): Promise<TimeseriesResponse> => {
  const search = new URLSearchParams();
  if (params?.window) search.set('window', params.window);
  if (params?.bucket) search.set('bucket', params.bucket);
  const query = search.toString();
  const url = `${apiUrl('/metrics/timeseries')}${query ? `?${query}` : ''}`;
  const response = await fetch(url);
  await assertOk(response);
  return (await response.json()) as TimeseriesResponse;
};

export const getMetricsSummary = fetchMetricsSummary;
export const getMetricsTimeseries = fetchMetricsTimeseries;

export const listTraces = (limit: number, offset: number) =>
  fetchTraces({ limit, offset });

export const getTrace = (traceId: string) => fetchTraceDetail(traceId);
