// Typed client for the AlphaMemoir FastAPI backend. All calls go through the
// Vite dev proxy at /api -> http://localhost:8000.

export type Action = 'buy' | 'sell' | 'hold'

export interface PortfolioSnapshot {
  timestamp: string
  cash: number
  equity: number
  total_pnl: number
  drawdown: number
}
export interface Position {
  symbol: string
  size: number
  avg_entry_price: number
  unrealized_pnl: number
  updated_at: string
}
export interface Portfolio {
  run_id: string
  strategy: string
  symbol: string
  latest: PortfolioSnapshot
  positions: Position[]
  equity_curve: PortfolioSnapshot[]
}

export interface Trade {
  id: number
  run_id: string
  timestamp: string
  symbol: string
  side: 'buy' | 'sell'
  size: number
  price: number
  fee: number
  slippage_cost: number
  strategy: string
  realized_pnl: number | null
  regime_at_entry: string | null
  rationale_summary: string | null
}
export interface TradeList {
  run_id: string
  total: number
  limit: number
  offset: number
  trades: Trade[]
}

export interface NodeTrace {
  node: string
  output: string
}
export interface RunCycleResult {
  run_id: string
  symbol: string
  action: Action
  size: number
  rationale: string
  confidence: number
  regime: string
  regime_summary: string
  trade_id: number | null
  executed_price: number | null
  equity: number
  memories_considered: number
  memory_write_id: string | null
  reasoning_trail: NodeTrace[]
}

export interface MemoryDocument {
  id: string
  type: string
  title: string | null
  content: string | null
  status: string
  metadata: Record<string, unknown>
  created_at: string | null
}
export interface MemoryDocuments {
  total: number
  counts_by_type: Record<string, number>
  documents: MemoryDocument[]
}

export interface MemorySearchResult {
  id: string
  document_id: string
  type: string | null
  content: string
  similarity: number
  metadata: Record<string, unknown>
}
export interface MemorySearch {
  query: string
  count: number
  results: MemorySearchResult[]
}

export interface MemoryStats {
  total_memories: number
  counts_by_type: Record<string, number>
  total_trades: number
  closed_trades: number
  win_rate: number
  total_reflections: number
  total_consolidations: number
}

export interface GraphNode {
  id: string
  kind: 'trade' | 'lesson' | 'consolidated'
  label: string
  regime: string | null
  outcome: string | null
  detail: string | null
}
export interface GraphEdge {
  source: string
  target: string
  kind: 'reflected_from' | 'consolidated_into' | 'cited_by'
}
export interface MemoryGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface ReflectionRow {
  id: number
  trade_id: number
  run_id: string
  created_at: string
  outcome: string
  return_pct: number
  diagnosis: string
  lesson_text: string
  lesson_memory_id: string
  confidence: number
}
export interface Reflections {
  total: number
  reflections: ReflectionRow[]
}

export interface ConsolidationRow {
  id: number
  created_at: string
  scope: string
  regime: string
  outcome: string
  meta_lesson: string
  consolidated_memory_id: string
  source_count: number
  confidence: number
}
export interface Consolidations {
  total: number
  consolidations: ConsolidationRow[]
}

export interface ConsolidateResult {
  consolidated_count: number
  consolidations: {
    consolidated_memory_id: string
    regime: string
    outcome: string
    meta_lesson: string
    source_memory_ids: string[]
    source_count: number
    confidence: number
  }[]
}

export interface PendingTrade {
  trade_id: number
  symbol: string
  side: string
  size: number
  price: number
  timestamp: string
  regime_at_entry: string | null
  realized_pnl: number | null
  days_held: number
  eligible: boolean
  reason: string
  days_until_eligible: number
}
export interface PendingReflection {
  lookback_days: number
  eligible_count: number
  waiting_count: number
  trades: PendingTrade[]
}

export interface PendingBucket {
  regime: string
  outcome: string
  lesson_count: number
  ready: boolean
  already_consolidated: boolean
}
export interface PendingConsolidation {
  min_group_size: number
  ready_count: number
  total_lessons: number
  buckets: PendingBucket[]
}

export interface ReflectResult {
  reflected_count: number
  reflections: {
    trade_id: number
    symbol: string
    outcome: string
    return_pct: number
    diagnosis: string
    lesson_text: string
    lesson_memory_id: string
    confidence: number
  }[]
}

export interface OHLCVBar {
  // UNIX seconds. A "YYYY-MM-DD" string would be read as a business day by
  // lightweight-charts, collapsing 24 hourly bars onto a single point.
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}
export interface TradeMarker {
  time: number
  price: number
  side: string
  size: number
  trade_id: number
}
export interface OHLCV {
  symbol: string
  timeframe: string
  exchange: string
  intraday: boolean
  last_bar_time: number | null
  fetched_at: string
  /** Served from the offline snapshot rather than a live fetch. */
  stale: boolean
  bars: OHLCVBar[]
  markers: TradeMarker[]
}

export interface Quote {
  symbol: string
  last: number
  change_24h_pct: number
  quote_volume: number
  exchange: string
  fetched_at: string
  stale: boolean
}

export const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'] as const
export const TIMEFRAMES = ['15m', '1h', '4h', '1d'] as const
export type Timeframe = (typeof TIMEFRAMES)[number]

/** FastAPI puts the useful part in `detail`. Surfacing only the status code turns
 *  "an agent could not produce a valid decision" into a bare "502" on screen. */
async function fail(res: Response, path: string): Promise<never> {
  let detail = ''
  try {
    detail = ((await res.json()) as { detail?: string }).detail ?? ''
  } catch {
    /* non-JSON body; fall back to the status line */
  }
  throw new Error(detail || `${res.status} ${res.statusText} on ${path}`)
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) await fail(res, path)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) await fail(res, path)
  return res.json() as Promise<T>
}

export const api = {
  portfolio: (runId?: string) => get<Portfolio>(`/portfolio${runId ? `?run_id=${runId}` : ''}`),
  trades: (limit = 100) => get<TradeList>(`/trades?limit=${limit}`),
  runCycle: (symbol = 'BTC/USDT', runId = 'paper-agent-v1', timeframe = '1h') =>
    post<RunCycleResult>('/run-cycle', { symbol, run_id: runId, timeframe }),

  ohlcv: (symbol = 'BTC/USDT', timeframe = '1h', limit = 300) =>
    get<OHLCV>(`/market/ohlcv?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`),
  quote: (symbol = 'BTC/USDT') => get<Quote>(`/market/quote?symbol=${encodeURIComponent(symbol)}`),

  memoryStats: () => get<MemoryStats>('/memory/stats'),
  memoryDocuments: (type?: string) =>
    get<MemoryDocuments>(`/memory/documents?limit=300${type ? `&type=${type}` : ''}`),
  memoryDocument: (id: string) => get<MemoryDocument>(`/memory/documents/${id}`),
  memorySearch: (q: string, type?: string) =>
    get<MemorySearch>(`/memory/search?q=${encodeURIComponent(q)}${type ? `&type=${type}` : ''}&limit=12`),
  memoryGraph: () => get<MemoryGraph>('/memory/graph'),
  reflections: () => get<Reflections>('/memory/reflections'),
  consolidations: () => get<Consolidations>('/memory/consolidations'),
  consolidate: () => post<ConsolidateResult>('/consolidate', { scope: 'ui' }),

  pendingReflection: (lookbackDays: number) =>
    get<PendingReflection>(`/reflect/pending?lookback_days=${lookbackDays}`),
  pendingConsolidation: () => get<PendingConsolidation>('/consolidate/pending'),
  reflect: (lookbackDays: number) =>
    post<ReflectResult>('/reflect', { max_trades: 10, lookback_days: lookbackDays }),
}
