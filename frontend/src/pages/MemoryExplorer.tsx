import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Sparkles, Layers, Database, Cpu, Lock, Boxes, Loader2, ArrowRight,
  Maximize2, BrainCircuit, CheckCircle2, Clock,
} from 'lucide-react'
import {
  Card, PageHeader, SectionTitle, StatTile, Skeleton, ErrorState, EmptyState,
  Pill, RegimeBadge, OutcomeBadge,
} from '../components/ui'
import { ProvenanceGraph } from '../components/ProvenanceGraph'
import { MemoryDetailModal } from '../components/MemoryDetailModal'
import {
  useGraph, useDocuments, useConsolidations, useStats,
  usePendingReflection, usePendingConsolidation, useRefreshAll,
} from '../lib/hooks'
import { api, type MemorySearch } from '../lib/api'
import { titleCase, shortId, tidyNumbers, fmtNum } from '../lib/format'

const SUGGESTIONS = [
  'position sizing in an uptrend',
  'what happens in volatile markets',
  'when the bull thesis is strong',
  'risk manager sizing cap',
]

const TYPE_META: Record<string, { label: string; color: string }> = {
  trade: { label: 'Trades', color: 'var(--am-trader)' },
  lesson: { label: 'Lessons', color: 'var(--am-cyan)' },
  consolidated_lesson: { label: 'Consolidated', color: 'var(--am-consolidate)' },
  regime_snapshot: { label: 'Regime snapshots', color: 'var(--am-pm)' },
}

export function MemoryExplorer() {
  const [openDoc, setOpenDoc] = useState<string | null>(null)
  const [lookback, setLookback] = useState(5)

  return (
    <div>
      <PageHeader
        eyebrow="Memory Explorer"
        title="Inside the living memory"
        sub="Everything here is queried live from the same self-hosted Supermemory instance the agents actually use — and you can grow it yourself: reflect, consolidate, and watch the graph react."
      />

      {/* ── 0. Basic stats ──────────────────────────────────────── */}
      <BasicStats />

      {/* ── 1. Ask the memory ───────────────────────────────────── */}
      <div className="mt-6">
        <AskTheMemory onOpen={setOpenDoc} />
      </div>

      {/* ── 2. Reflect & Consolidate ────────────────────────────── */}
      <div className="mt-6">
        <SectionTitle hint="grow the memory — the graph below updates instantly">Reflect &amp; consolidate</SectionTitle>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ReflectPanel lookback={lookback} setLookback={setLookback} />
          <ConsolidatePanel />
        </div>
      </div>

      {/* ── 3. Provenance graph ─────────────────────────────────── */}
      <div className="mt-6">
        <SectionTitle hint="click a node to trace its connections">Learning provenance graph</SectionTitle>
        <ProvenancePanel />
      </div>

      {/* ── 4. Consolidation lens + living memory feed ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6 items-stretch">
        <ConsolidationLens />
        <MemoryFeed onOpen={setOpenDoc} />
      </div>

      {/* ── 5. System internals ─────────────────────────────────── */}
      <div className="mt-6">
        <SystemInternals />
      </div>

      {openDoc && <MemoryDetailModal documentId={openDoc} onClose={() => setOpenDoc(null)} />}
    </div>
  )
}

/* ── 0. Basic stats ───────────────────────────────────────────── */

function BasicStats() {
  const stats = useStats()
  if (stats.isError) return <ErrorState error={stats.error} />

  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.isLoading ? (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[104px]" />)
        ) : (
          <>
            <StatTile label="Total memories" value={stats.data!.total_memories} sub="stored in Supermemory" accent="accent" icon={<Database size={16} />} />
            <StatTile label="Lessons learned" value={stats.data!.counts_by_type['lesson'] ?? 0} sub="from reflection" icon={<BrainCircuit size={16} />} />
            <StatTile label="Consolidated insights" value={stats.data!.total_consolidations} sub="higher-order rules" accent="accent" icon={<Layers size={16} />} />
            <StatTile label="Trades executed" value={stats.data!.counts_by_type['trade'] ?? 0} sub={`${stats.data!.total_reflections} reflected`} icon={<Sparkles size={16} />} />
          </>
        )}
      </div>

      <Card className="p-5 mt-4" glow>
        <SectionTitle hint={stats.data ? `${stats.data.total_memories} documents` : undefined}>Memory composition</SectionTitle>
        {stats.isLoading ? (
          <Skeleton className="h-16" />
        ) : (
          <Composition counts={stats.data?.counts_by_type ?? {}} total={stats.data?.total_memories ?? 0} />
        )}
      </Card>
    </>
  )
}

function Composition({ counts, total }: { counts: Record<string, number>; total: number }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1])
  if (!total) return <EmptyState title="No memories yet" />
  return (
    <div className="flex flex-col gap-4">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-surface-3">
        {entries.map(([type, n]) => (
          <div
            key={type}
            className="h-full first:rounded-l-full last:rounded-r-full"
            style={{ width: `${(n / total) * 100}%`, background: TYPE_META[type]?.color ?? 'var(--am-blue)', marginRight: 2 }}
            title={`${type}: ${n}`}
          />
        ))}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {entries.map(([type, n]) => (
          <div key={type} className="flex items-center gap-2.5">
            <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: TYPE_META[type]?.color ?? 'var(--am-blue)' }} />
            <div className="leading-tight">
              <div className="text-lg font-bold tabular-nums text-text">{n}</div>
              <div className="text-xs text-muted">{TYPE_META[type]?.label ?? titleCase(type)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── 1. Ask the memory ────────────────────────────────────────── */

function AskTheMemory({ onOpen }: { onOpen: (id: string) => void }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<MemorySearch | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (query: string) => {
    if (!query.trim()) return
    setQ(query)
    setBusy(true)
    try {
      setResults(await api.memorySearch(query))
    } catch {
      setResults({ query, count: 0, results: [] })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5" glow>
      <SectionTitle hint="hybrid semantic search">Ask the memory</SectionTitle>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          run(q)
        }}
        className="flex items-center gap-2 rounded-xl border border-border bg-surface-2 px-3 py-2 focus-within:border-accent transition-colors"
      >
        <Search size={18} className="text-faint" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask in your own words — meaning, not keywords…"
          className="flex-1 bg-transparent text-sm text-text placeholder:text-faint outline-none"
        />
        <button type="submit" className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-contrast hover:bg-accent-hover transition-colors flex items-center gap-1.5">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Search
        </button>
      </form>

      {!results && (
        <div className="flex flex-wrap gap-2 mt-3">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => run(s)} className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted hover:text-text hover:border-accent transition-colors">
              {s}
            </button>
          ))}
        </div>
      )}

      {results && (
        <div className="mt-4 space-y-2 max-h-[420px] overflow-y-auto pr-1">
          {results.results.length === 0 ? (
            <EmptyState title="No matches" hint="Try a different phrasing." />
          ) : (
            results.results.map((r) => (
              <button
                key={r.id}
                onClick={() => onOpen(r.document_id)}
                className="w-full text-left rounded-lg border border-border bg-surface-2 p-3 hover:border-accent hover:bg-surface-3 transition-colors cursor-pointer group"
                title="Open the full memory"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <Pill tone="accent">{titleCase(r.type ?? 'memory')}</Pill>
                  <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, r.similarity * 100)}%`, background: 'linear-gradient(90deg, var(--am-blue), var(--am-cyan))' }} />
                  </div>
                  <span className="tnum text-xs font-semibold text-cyan">{r.similarity.toFixed(2)}</span>
                  <Maximize2 size={12} className="text-faint opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="text-sm text-text leading-snug">{tidyNumbers(r.content)}</p>
              </button>
            ))
          )}
        </div>
      )}
    </Card>
  )
}

/* ── 2a. Reflect ──────────────────────────────────────────────── */

const LOOKBACKS = [0, 3, 5, 7]

function ReflectPanel({ lookback, setLookback }: { lookback: number; setLookback: (n: number) => void }) {
  const pending = usePendingReflection(lookback)
  const refreshAll = useRefreshAll()
  const [done, setDone] = useState<number | null>(null)

  const reflect = useMutation({
    mutationFn: () => api.reflect(lookback),
    onSuccess: (data) => {
      setDone(data.reflected_count)
      setTimeout(() => setDone(null), 4000)
      refreshAll()
    },
  })

  const eligible = pending.data?.eligible_count ?? 0

  return (
    <Card className="p-5 flex flex-col h-[440px]">
      <SectionTitle hint={pending.data ? `${pending.data.trades.length} undiagnosed` : undefined}>
        <span className="flex items-center gap-2">
          <BrainCircuit size={14} style={{ color: 'var(--am-reflect)' }} /> Reflect — trades to diagnose
        </span>
      </SectionTitle>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="text-xs text-faint">Lookback</span>
        {LOOKBACKS.map((d) => (
          <button
            key={d}
            onClick={() => setLookback(d)}
            className={`rounded-full px-2.5 py-1 text-xs font-semibold transition-colors ${
              lookback === d ? 'bg-accent text-accent-contrast' : 'bg-surface-2 text-muted hover:text-text'
            }`}
          >
            {d}d
          </button>
        ))}
        <span className="text-xs text-faint ml-auto">eligible once closed, or open ≥ lookback</span>
      </div>

      <div className="flex-1 min-h-0 space-y-2 overflow-y-auto pr-1">
        {pending.isLoading ? (
          <Skeleton className="h-24" />
        ) : pending.data?.trades.length ? (
          pending.data.trades.map((t) => (
            <div
              key={t.trade_id}
              className="rounded-lg border bg-surface-2 p-3"
              style={{ borderColor: t.eligible ? 'var(--am-reflect)' : 'var(--border)' }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone={t.side === 'buy' ? 'gain' : 'loss'}>{t.side}</Pill>
                <span className="tnum text-sm text-text">{fmtNum(t.size, 2)} {t.symbol}</span>
                <span className="tnum text-xs text-muted">@ {fmtNum(t.price, 2)}</span>
                <RegimeBadge regime={t.regime_at_entry} />
                <span className="ml-auto">
                  {t.eligible ? (
                    <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: 'var(--am-reflect)' }}>
                      <CheckCircle2 size={13} /> ready · {t.reason}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-faint">
                      <Clock size={13} /> in {t.days_until_eligible}d
                    </span>
                  )}
                </span>
              </div>
            </div>
          ))
        ) : (
          <EmptyState title="Every trade has been diagnosed" hint="Run a new cycle to create more." />
        )}
      </div>

      <button
        onClick={() => reflect.mutate()}
        disabled={reflect.isPending || eligible === 0}
        className={`mt-4 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
          eligible === 0 && !reflect.isPending
            ? 'bg-surface-3 text-faint cursor-not-allowed border border-border'
            : 'text-accent-contrast'
        }`}
        style={
          eligible > 0 || reflect.isPending
            ? { background: 'var(--am-reflect)', boxShadow: '0 8px 24px -12px var(--am-reflect)' }
            : undefined
        }
      >
        {reflect.isPending ? <Loader2 size={16} className="animate-spin" /> : <BrainCircuit size={16} />}
        {reflect.isPending ? 'Diagnosing…' : eligible ? `Reflect on ${eligible} trade${eligible > 1 ? 's' : ''}` : 'Nothing eligible yet'}
      </button>

      <AnimatePresence>
        {done !== null && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-2 text-center text-xs font-semibold" style={{ color: 'var(--am-reflect)' }}>
            ✓ Wrote {done} new lesson{done === 1 ? '' : 's'} into Supermemory
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

/* ── 2b. Consolidate ──────────────────────────────────────────── */

function ConsolidatePanel() {
  const pending = usePendingConsolidation()
  const refreshAll = useRefreshAll()
  const [done, setDone] = useState<number | null>(null)

  const consolidate = useMutation({
    mutationFn: api.consolidate,
    onSuccess: (data) => {
      setDone(data.consolidated_count)
      setTimeout(() => setDone(null), 4000)
      refreshAll()
    },
  })

  const ready = pending.data?.ready_count ?? 0
  const threshold = pending.data?.min_group_size ?? 2

  return (
    <Card className="p-5 flex flex-col h-[440px]">
      <SectionTitle hint={pending.data ? `${pending.data.total_lessons} lessons` : undefined}>
        <span className="flex items-center gap-2">
          <Layers size={14} style={{ color: 'var(--am-consolidate)' }} /> Consolidate — batches to distil
        </span>
      </SectionTitle>

      <p className="text-xs text-faint mb-3">
        Lessons are grouped by regime + outcome. A batch is ready once it holds ≥ {threshold} lessons that haven’t been distilled before.
      </p>

      <div className="flex-1 min-h-0 space-y-2 overflow-y-auto pr-1">
        {pending.isLoading ? (
          <Skeleton className="h-24" />
        ) : pending.data?.buckets.length ? (
          pending.data.buckets.map((b) => (
            <div
              key={`${b.regime}-${b.outcome}`}
              className="rounded-lg border bg-surface-2 p-3"
              style={{ borderColor: b.ready ? 'var(--am-consolidate)' : 'var(--border)' }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <RegimeBadge regime={b.regime} />
                <OutcomeBadge outcome={b.outcome} />
                <span className="ml-auto flex items-center gap-2">
                  <span className="flex gap-0.5">
                    {Array.from({ length: Math.max(threshold, Math.min(b.lesson_count, 6)) }).map((_, i) => (
                      <span
                        key={i}
                        className="h-3.5 w-1.5 rounded-sm"
                        style={{ background: i < b.lesson_count ? 'var(--am-consolidate)' : 'var(--surface-3)' }}
                      />
                    ))}
                  </span>
                  <span className="tnum text-xs font-semibold text-text">{b.lesson_count}</span>
                </span>
              </div>
              <div className="mt-1.5 text-xs">
                {b.ready ? (
                  <span className="flex items-center gap-1 font-semibold" style={{ color: 'var(--am-consolidate)' }}>
                    <CheckCircle2 size={13} /> ready to distil
                  </span>
                ) : b.already_consolidated ? (
                  <span className="text-faint">already distilled into a meta-lesson</span>
                ) : (
                  <span className="text-faint">needs {threshold - b.lesson_count} more lesson{threshold - b.lesson_count === 1 ? '' : 's'}</span>
                )}
              </div>
            </div>
          ))
        ) : (
          <EmptyState title="No lessons yet" hint="Reflect on a trade first — consolidation needs lessons to distil." />
        )}
      </div>

      <button
        onClick={() => consolidate.mutate()}
        disabled={consolidate.isPending || ready === 0}
        className={`mt-4 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
          ready === 0 && !consolidate.isPending
            ? 'bg-surface-3 text-faint cursor-not-allowed border border-border'
            : 'text-accent-contrast'
        }`}
        style={
          ready > 0 || consolidate.isPending
            ? { background: 'var(--am-consolidate)', boxShadow: '0 8px 24px -12px var(--am-consolidate)' }
            : undefined
        }
      >
        {consolidate.isPending ? <Loader2 size={16} className="animate-spin" /> : <Layers size={16} />}
        {consolidate.isPending ? 'Distilling…' : ready ? `Consolidate ${ready} batch${ready > 1 ? 'es' : ''}` : 'No batch ready yet'}
      </button>

      <AnimatePresence>
        {done !== null && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-2 text-center text-xs font-semibold" style={{ color: 'var(--am-consolidate)' }}>
            ✓ Distilled {done} higher-order meta-lesson{done === 1 ? '' : 's'}
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

/* ── 3. Provenance graph ──────────────────────────────────────── */

const LEGEND = [
  { label: 'Trade', color: 'var(--am-trader)' },
  { label: 'Lesson', color: 'var(--am-cyan)' },
  { label: 'Meta-lesson', color: 'var(--am-consolidate)' },
]

function ProvenancePanel() {
  const graph = useGraph()
  return (
    <Card className="p-5" glow>
      <div className="flex flex-wrap items-center gap-4 mb-3">
        {LEGEND.map((l) => (
          <span key={l.label} className="flex items-center gap-1.5 text-xs text-muted">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
        <span className="text-xs text-faint ml-auto">
          {graph.data ? `${graph.data.nodes.length} nodes · ${graph.data.edges.length} real edges` : ''}
        </span>
      </div>
      {graph.isLoading ? (
        <Skeleton className="h-[520px]" />
      ) : graph.isError ? (
        <ErrorState error={graph.error} />
      ) : graph.data && graph.data.nodes.length ? (
        <ProvenanceGraph graph={graph.data} />
      ) : (
        <EmptyState title="No provenance yet" hint="Reflect on a trade to grow the graph." />
      )}
      <p className="text-xs text-faint mt-3">
        Every edge is id-traceable: a trade → the lesson reflected from it, lessons → the meta-lesson that consolidated them, and a past lesson → a later trade whose decision actually cited it.
      </p>
    </Card>
  )
}

/* ── 4a. Consolidation lens ───────────────────────────────────── */

function ConsolidationLens() {
  const consolidations = useConsolidations()

  return (
    <Card className="p-5 flex flex-col h-[560px]">
      <SectionTitle hint={consolidations.data ? `${consolidations.data.total} meta-lessons` : undefined}>
        Consolidation lens
      </SectionTitle>

      <div className="flex-1 min-h-0 space-y-3 overflow-y-auto pr-1">
        {consolidations.isLoading ? (
          <Skeleton className="h-40" />
        ) : consolidations.data?.consolidations.length ? (
          consolidations.data.consolidations.map((c) => (
            <div key={c.id} className="rounded-lg border border-border bg-surface-2 p-3">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="grid h-6 w-6 place-items-center rounded" style={{ background: 'color-mix(in srgb, var(--am-consolidate) 18%, transparent)' }}>
                  <Layers size={13} style={{ color: 'var(--am-consolidate)' }} />
                </span>
                <RegimeBadge regime={c.regime} />
                <OutcomeBadge outcome={c.outcome} />
                <span className="ml-auto text-xs text-faint flex items-center gap-1">
                  {c.source_count} <ArrowRight size={11} /> 1
                </span>
              </div>
              <p className="text-sm text-text leading-snug">{tidyNumbers(c.meta_lesson)}</p>
            </div>
          ))
        ) : (
          <EmptyState title="No consolidated insights yet" hint="Distil a batch above to create the first." />
        )}
      </div>

      <p className="text-xs text-faint mt-3 shrink-0">
        Our Consolidation Agent merges related lessons into higher-order meta-lessons and writes them back into Supermemory.
      </p>
    </Card>
  )
}

/* ── 4b. Living memory feed ───────────────────────────────────── */

const FEED_TYPES = ['all', 'lesson', 'consolidated_lesson', 'trade', 'regime_snapshot']

function MemoryFeed({ onOpen }: { onOpen: (id: string) => void }) {
  const [type, setType] = useState('all')
  const docs = useDocuments(type === 'all' ? undefined : type)
  const stats = useStats()

  return (
    <Card className="p-5 flex flex-col h-[560px]">
      <SectionTitle hint={docs.data ? `${docs.data.total} shown · click to open` : undefined}>Living memory feed</SectionTitle>

      <div className="flex flex-wrap gap-1.5 mb-3 shrink-0">
        {FEED_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
              type === t ? 'bg-accent text-accent-contrast' : 'bg-surface-2 text-muted hover:text-text'
            }`}
          >
            {t === 'all' ? `All${stats.data ? ` · ${stats.data.total_memories}` : ''}` : titleCase(t)}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 space-y-2 overflow-y-auto pr-1">
        {docs.isLoading ? (
          <Skeleton className="h-40" />
        ) : docs.data?.documents.length ? (
          docs.data.documents.map((d) => (
            <button
              key={d.id}
              onClick={() => onOpen(d.id)}
              className="w-full text-left rounded-lg border border-border bg-surface-2 p-3 hover:border-accent hover:bg-surface-3 transition-colors cursor-pointer group"
              title="Open the full memory"
            >
              <div className="flex items-center gap-2 mb-1">
                <Pill tone="neutral">{titleCase(d.type)}</Pill>
                <span className={`ml-auto flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider ${d.status === 'done' ? 'text-gain' : 'text-warn'}`}>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: d.status === 'done' ? 'var(--am-gain)' : 'var(--am-warn)' }} />
                  {d.status}
                </span>
                <span className="text-[10px] text-faint font-mono">{shortId(d.id)}</span>
                <Maximize2 size={12} className="text-faint opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-xs text-text leading-snug line-clamp-2">{tidyNumbers(d.content ?? d.title ?? '—')}</p>
            </button>
          ))
        ) : (
          <EmptyState title="No documents" />
        )}
      </div>
    </Card>
  )
}

/* ── 5. System internals ──────────────────────────────────────── */

const INTERNALS = [
  { icon: Cpu, label: 'Local embeddings', value: 'bge-base-en-v1.5 · 768-dim ONNX' },
  { icon: Lock, label: 'Storage', value: 'Encrypted, on-device' },
  { icon: Boxes, label: 'Container', value: 'trading_system' },
  { icon: Database, label: 'Self-hosted', value: 'Supermemory · localhost' },
]

function SystemInternals() {
  return (
    <Card className="p-5">
      <SectionTitle>System internals</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {INTERNALS.map((it) => (
          <div key={it.label} className="flex items-start gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-surface-2 shrink-0">
              <it.icon size={15} className="text-accent" />
            </span>
            <div className="leading-tight">
              <div className="text-xs text-faint">{it.label}</div>
              <div className="text-sm font-medium text-text">{it.value}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
