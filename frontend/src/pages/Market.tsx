import { useState } from 'react'
import { ChevronDown, WifiOff } from 'lucide-react'
import { Card, PageHeader, SectionTitle, StatTile, Skeleton, ErrorState, EmptyState, Pill, RegimeBadge } from '../components/ui'
import { PriceChart } from '../components/PriceChart'
import { useOHLCV, usePortfolio, useQuote, useTrades } from '../lib/hooks'
import { fmtMoney, fmtNum, fmtPct, fmtDateTime, fmtAgo, fmtBarTime, fmtCompact, tidyNumbers } from '../lib/format'
import { SYMBOLS, TIMEFRAMES, type Trade } from '../lib/api'

export function Market() {
  const [symbol, setSymbol] = useState<string>(SYMBOLS[0])
  const [timeframe, setTimeframe] = useState<string>('1h')

  const ohlcv = useOHLCV(symbol, timeframe)
  const quote = useQuote(symbol)
  const portfolio = usePortfolio()
  const trades = useTrades()

  const latest = portfolio.data?.latest
  const stale = ohlcv.data?.stale || quote.data?.stale
  const up = (quote.data?.change_24h_pct ?? 0) >= 0

  return (
    <div>
      <PageHeader
        eyebrow="Market & Ledger"
        title="The live tape the agents trade on"
        sub="Real candles streaming from a public exchange, the book they produced, and every fill on the record."
      />

      {/* ── The live ticker ─────────────────────────────────────────── */}
      <Card className="p-5 mb-6" glow>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-lg font-bold tracking-tight text-text">{symbol}</span>
              {stale ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-warn/40 bg-warn/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-warn">
                  <WifiOff size={10} /> cached
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-gain/40 bg-gain/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-gain">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gain opacity-75" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-gain" />
                  </span>
                  Live
                </span>
              )}
            </div>

            <div className="mt-2 flex items-baseline gap-3">
              <span className="tnum text-[34px] font-bold leading-none tracking-tight text-text">
                {quote.data ? fmtMoney(quote.data.last) : '—'}
              </span>
              {quote.data && (
                <span className={`tnum text-sm font-semibold ${up ? 'text-gain' : 'text-loss'}`}>
                  {fmtPct(quote.data.change_24h_pct)} <span className="text-faint font-normal">24h</span>
                </span>
              )}
            </div>

            <div className="mt-2 text-xs text-faint">
              {ohlcv.data?.exchange ?? '…'} · {quote.data ? `vol ${fmtCompact(quote.data.quote_volume)}` : '…'}
              {quote.data && <> · updated {fmtAgo(quote.data.fetched_at)}</>}
            </div>
          </div>

          <div className="flex flex-col items-end gap-2">
            <ChipGroup options={SYMBOLS} value={symbol} onChange={setSymbol} />
            <ChipGroup options={TIMEFRAMES} value={timeframe} onChange={setTimeframe} />
          </div>
        </div>

        <div className="mt-5">
          {ohlcv.isLoading && !ohlcv.data ? (
            <Skeleton className="h-[380px]" />
          ) : ohlcv.isError ? (
            <ErrorState error={ohlcv.error} />
          ) : (
            <PriceChart
              bars={ohlcv.data!.bars}
              markers={ohlcv.data!.markers}
              intraday={ohlcv.data!.intraday}
            />
          )}
        </div>
        {ohlcv.data && (
          <div className="mt-2 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center text-xs text-faint">
            <span>
              {ohlcv.data.bars.length} × {ohlcv.data.timeframe} bars · {ohlcv.data.markers.length} agent{' '}
              {ohlcv.data.markers.length === 1 ? 'entry' : 'entries'} marked
            </span>
            {ohlcv.data.last_bar_time && (
              <>
                <span className="text-border">|</span>
                <span>
                  latest candle{' '}
                  <span className="tnum font-medium text-muted">{fmtBarTime(ohlcv.data.last_bar_time)}</span>
                  {!ohlcv.data.stale && <span className="text-gain"> · forming</span>}
                </span>
                <span className="text-border">|</span>
                <span>refreshes every 20s</span>
              </>
            )}
          </div>
        )}
      </Card>

      {/* ── The book ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {portfolio.isLoading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[104px]" />)
        ) : (
          <>
            <StatTile label="Equity" value={latest ? fmtMoney(latest.equity) : '—'} sub={portfolio.data?.run_id} accent="accent" />
            <StatTile label="Total P&L" value={latest ? fmtMoney(latest.total_pnl) : '—'} accent={latest && latest.total_pnl >= 0 ? 'gain' : 'loss'} />
            <StatTile label="Cash" value={latest ? fmtMoney(latest.cash) : '—'} />
            <StatTile label="Open positions" value={portfolio.data?.positions.length ?? 0} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-5">
          <SectionTitle>Positions</SectionTitle>
          {portfolio.data?.positions.length ? (
            <div className="space-y-3">
              {portfolio.data.positions.map((p) => (
                <div key={p.symbol} className="flex items-center justify-between rounded-lg bg-surface-2 p-3">
                  <div>
                    <div className="font-semibold text-text">{p.symbol}</div>
                    <div className="text-xs text-muted tnum">
                      {fmtNum(p.size, 4)} @ {fmtMoney(p.avg_entry_price)}
                    </div>
                  </div>
                  <Pill tone={p.unrealized_pnl >= 0 ? 'gain' : 'loss'}>{fmtMoney(p.unrealized_pnl)}</Pill>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No open positions" />
          )}
        </Card>

        <Card className="p-5 lg:col-span-2">
          <SectionTitle hint={trades.data ? `${trades.data.total} fills` : undefined}>Trade ledger</SectionTitle>
          {trades.isLoading ? (
            <Skeleton className="h-40" />
          ) : trades.data?.trades.length ? (
            <Ledger trades={trades.data.trades} />
          ) : (
            <EmptyState title="No trades on the ledger yet" hint="Run a cycle from Live Orchestration to place one." />
          )}
        </Card>
      </div>
    </div>
  )
}

function ChipGroup({
  options,
  value,
  onChange,
}: {
  options: readonly string[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-surface-2 p-0.5">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
            value === opt ? 'bg-accent text-accent-contrast' : 'text-muted hover:text-text'
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

function Ledger({ trades }: { trades: Trade[] }) {
  const [open, setOpen] = useState<number | null>(trades[0]?.id ?? null)
  return (
    <div className="divide-y divide-border">
      <div className="grid grid-cols-[auto_1.2fr_1fr_1fr_1fr_auto] gap-3 px-1 pb-2 text-[11px] font-semibold uppercase tracking-wider text-faint">
        <span>Side</span>
        <span>Symbol</span>
        <span>Size</span>
        <span>Price</span>
        <span>Regime</span>
        <span>P&L</span>
      </div>
      {trades.map((t) => (
        <div key={t.id}>
          <button
            onClick={() => setOpen(open === t.id ? null : t.id)}
            className="grid w-full grid-cols-[auto_1.2fr_1fr_1fr_1fr_auto] items-center gap-3 px-1 py-2.5 text-left text-sm hover:bg-surface-2 rounded-md transition-colors"
          >
            <Pill tone={t.side === 'buy' ? 'gain' : 'loss'}>{t.side}</Pill>
            <span className="text-xs font-medium text-muted">{t.symbol}</span>
            <span className="tnum text-text">{fmtNum(t.size, 4)}</span>
            <span className="tnum text-text">{fmtMoney(t.price)}</span>
            <span className="text-xs"><RegimeBadge regime={t.regime_at_entry} /></span>
            <span className="flex items-center gap-1.5 justify-end">
              <span className={`tnum ${t.realized_pnl == null ? 'text-faint' : t.realized_pnl >= 0 ? 'text-gain' : 'text-loss'}`}>
                {t.realized_pnl == null ? 'open' : fmtMoney(t.realized_pnl)}
              </span>
              <ChevronDown size={14} className={`text-faint transition-transform ${open === t.id ? 'rotate-180' : ''}`} />
            </span>
          </button>
          {open === t.id && (
            <div className="px-1 pb-3 pt-1 text-xs text-muted grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
              <Detail label="Trade ID" value={`#${t.id}`} />
              <Detail label="Timestamp" value={fmtDateTime(t.timestamp)} />
              <Detail label="Fee" value={fmtMoney(t.fee)} />
              <Detail label="Slippage" value={fmtMoney(t.slippage_cost)} />
              <Detail label="Strategy" value={t.strategy} />
              <Detail label="Run" value={t.run_id} />
              {t.rationale_summary && (
                <div className="sm:col-span-2 mt-1 rounded-md bg-surface-2 p-2.5 text-text leading-relaxed">
                  {tidyNumbers(t.rationale_summary)}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-border/50 py-0.5">
      <span className="text-faint">{label}</span>
      <span className="text-text font-medium text-right">{value}</span>
    </div>
  )
}
