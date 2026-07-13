import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Play, Loader2, TrendingUp, TrendingDown, Radar, ShieldCheck, ArrowDownUp, Briefcase, CheckCircle2, ArrowDown, AlertTriangle } from 'lucide-react'
import { Card, PageHeader, Pill, ActionBadge, RegimeBadge } from '../components/ui'
import { api, SYMBOLS, TIMEFRAMES, type RunCycleResult } from '../lib/api'
import { fmtMoney, fmtNum, tidyNumbers } from '../lib/format'
import { useQuote, useRefreshAll } from '../lib/hooks'

type Agent = { key: string; name: string; role: string; color: string; icon: typeof Radar }

const STAGES: Agent[][] = [
  [{ key: 'market_analyst', name: 'Market Analyst', role: 'classifies the regime', color: 'var(--am-analyst)', icon: Radar }],
  [
    { key: 'researcher_bull', name: 'Researcher · Bull', role: 'argues the long case', color: 'var(--am-bull)', icon: TrendingUp },
    { key: 'researcher_bear', name: 'Researcher · Bear', role: 'argues the short case', color: 'var(--am-bear)', icon: TrendingDown },
  ],
  [{ key: 'risk_manager', name: 'Risk Manager', role: 'sets the size envelope', color: 'var(--am-risk)', icon: ShieldCheck }],
  [{ key: 'trader', name: 'Trader', role: 'sizes the position', color: 'var(--am-trader)', icon: ArrowDownUp }],
  [{ key: 'portfolio_manager', name: 'Portfolio Manager', role: 'enforces the hard cap', color: 'var(--am-pm)', icon: Briefcase }],
]

function summarize(node: string, raw: string): string {
  const clean = (s: string) => tidyNumbers(s)
  try {
    const o = JSON.parse(raw)
    if (node === 'market_analyst') return clean(`${(o.regime ?? '').replace(/_/g, ' ')} — ${o.summary ?? ''}`)
    if (node.startsWith('researcher')) return clean(o.thesis ?? raw)
    if (node === 'risk_manager') return clean(`${o.approved ? 'Approved' : 'Vetoed'} — ${o.reasoning ?? ''}`)
    if (node === 'trader' || node === 'portfolio_manager' || node === 'hold')
      return clean(`${(o.action ?? '').toUpperCase()} ${o.size ? fmtNum(o.size, 2) : ''} — ${o.rationale ?? ''}`)
    return clean(raw)
  } catch {
    return clean(raw)
  }
}

export function Orchestration() {
  const [symbol, setSymbol] = useState<string>(SYMBOLS[0])
  const [timeframe, setTimeframe] = useState<string>('1h')
  const [result, setResult] = useState<RunCycleResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revealed, setRevealed] = useState(0)
  const [running, setRunning] = useState(false)
  const timers = useRef<number[]>([])
  const refreshAll = useRefreshAll()

  const quote = useQuote(symbol)

  const run = useCallback(async () => {
    timers.current.forEach(clearTimeout)
    timers.current = []
    setRunning(true)
    setResult(null)
    setError(null)
    setRevealed(0)
    try {
      const cycle = await api.runCycle(symbol, 'live-demo', timeframe)
      setResult(cycle)
      // staged reveal, one trace entry at a time
      cycle.reasoning_trail.forEach((_, i) => {
        timers.current.push(window.setTimeout(() => setRevealed(i + 1), 650 * (i + 1)))
      })
      timers.current.push(
        window.setTimeout(() => {
          setRunning(false)
          // A cycle writes a trade memory and a regime snapshot into Supermemory,
          // so the Memory Explorer is stale too -- not just the ledger.
          refreshAll()
        }, 650 * (cycle.reasoning_trail.length + 1)),
      )
    } catch (e) {
      // A live LLM can still fail to produce a valid decision. Say so out loud --
      // swallowing it leaves the judge staring at a button that did nothing.
      setError(e instanceof Error ? e.message : 'The cycle failed.')
      setRunning(false)
    }
  }, [refreshAll, symbol, timeframe])

  const outputs = new Map(result?.reasoning_trail.slice(0, revealed).map((t) => [t.node, t.output]))

  return (
    <div>
      <PageHeader
        eyebrow="Live Orchestration"
        title="Watch the agents think"
        sub="Run a real cycle. Six agents reason in sequence over live market data and retrieved memory, and the decision emerges in front of you."
        right={
          <button
            onClick={run}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-contrast hover:bg-accent-hover transition-colors disabled:opacity-60"
            style={{ boxShadow: '0 8px 24px -10px var(--glow)' }}
          >
            {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {running ? 'Running…' : 'Run new cycle'}
          </button>
        }
      />

      {/* ── What the agents will be handed ───────────────────────────── */}
      <Card className="p-4 mb-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-faint">Market</span>
            <ChipGroup options={SYMBOLS} value={symbol} onChange={setSymbol} disabled={running} />
            <ChipGroup options={TIMEFRAMES} value={timeframe} onChange={setTimeframe} disabled={running} />
          </div>
          <div className="text-xs text-muted">
            {quote.data ? (
              <>
                <span className="tnum font-semibold text-text">{fmtMoney(quote.data.last)}</span>
                <span className={quote.data.change_24h_pct >= 0 ? 'text-gain' : 'text-loss'}>
                  {' '}
                  {quote.data.change_24h_pct >= 0 ? '+' : ''}
                  {quote.data.change_24h_pct.toFixed(2)}%
                </span>
                <span className="text-faint"> · live from {quote.data.exchange}</span>
              </>
            ) : (
              <span className="text-faint">loading price…</span>
            )}
          </div>
        </div>
      </Card>

      {error && (
        <Card className="p-4 mb-5 border-loss/40">
          <div className="flex items-start gap-2.5 text-sm">
            <AlertTriangle size={16} className="text-loss shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-text">The cycle didn’t complete</div>
              <div className="mt-0.5 text-muted">{error}</div>
            </div>
          </div>
        </Card>
      )}

      {result && revealed >= result.reasoning_trail.length && <DecisionBanner result={result} />}

      <div className="flex flex-col items-center gap-2 mt-2">
        {STAGES.map((stage, si) => (
          <div key={si} className="w-full flex flex-col items-center gap-2">
            <div className="flex flex-wrap justify-center gap-3 w-full">
              {stage.map((agent) => (
                <AgentCard key={agent.key} agent={agent} output={outputs.get(agent.key)} active={outputs.has(agent.key)} />
              ))}
            </div>
            {si < STAGES.length - 1 && <ArrowDown size={18} className="text-faint" />}
          </div>
        ))}
      </div>

      {!result && !running && !error && (
        <p className="text-center text-sm text-faint mt-6">
          Press “Run new cycle” to place a live paper trade on {symbol} and watch the reasoning unfold.
        </p>
      )}
    </div>
  )
}

function ChipGroup({
  options,
  value,
  onChange,
  disabled,
}: {
  options: readonly string[]
  value: string
  onChange: (v: string) => void
  disabled?: boolean
}) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-surface-2 p-0.5">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          disabled={disabled}
          className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors disabled:opacity-50 ${
            value === opt ? 'bg-accent text-accent-contrast' : 'text-muted hover:text-text'
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

function AgentCard({ agent, output, active }: { agent: Agent; output?: string; active: boolean }) {
  const Icon = agent.icon
  return (
    <motion.div
      initial={false}
      animate={active ? { opacity: 1, scale: 1 } : { opacity: 0.5, scale: 0.99 }}
      transition={{ duration: 0.3 }}
      className="am-card p-4 w-full max-w-[440px]"
      style={active ? { borderColor: agent.color, boxShadow: `0 0 0 1px ${agent.color}33, 0 10px 30px -16px ${agent.color}` } : undefined}
    >
      <div className="flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg shrink-0" style={{ background: `color-mix(in srgb, ${agent.color} 16%, transparent)` }}>
          <Icon size={18} style={{ color: agent.color }} />
        </span>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-text">{agent.name}</div>
          <div className="text-xs text-muted">{agent.role}</div>
        </div>
        {active && (
          <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="ml-auto">
            <CheckCircle2 size={16} style={{ color: agent.color }} />
          </motion.span>
        )}
      </div>
      {active && output && (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="text-xs text-text leading-relaxed mt-3 rounded-lg bg-surface-2 p-2.5 overflow-hidden"
        >
          {summarize(agent.key, output)}
        </motion.p>
      )}
    </motion.div>
  )
}

function DecisionBanner({ result }: { result: RunCycleResult }) {
  return (
    <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="p-5 mb-5" glow>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs uppercase tracking-wider text-faint">Decision</span>
            <ActionBadge action={result.action} />
            {result.size > 0 && <span className="tnum text-sm font-semibold text-text">{fmtNum(result.size, 2)} units</span>}
          </div>
          <div className="h-8 w-px bg-border hidden sm:block" />
          <RegimeBadge regime={result.regime} />
          <div className="h-8 w-px bg-border hidden sm:block" />
          <span className="text-xs text-muted">
            confidence <span className="tnum font-semibold text-cyan">{(result.confidence * 100).toFixed(0)}%</span>
          </span>
          <span className="text-xs text-muted">
            <Pill tone="accent">{result.memories_considered} memories recalled</Pill>
          </span>
        </div>
        {result.rationale && <p className="text-sm text-text leading-relaxed mt-3">{tidyNumbers(result.rationale)}</p>}
      </Card>
    </motion.div>
  )
}
