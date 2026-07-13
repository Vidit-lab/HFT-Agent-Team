import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Users, BrainCircuit, Layers, Search, ShieldCheck, GitBranch,
  ArrowRight, Workflow, Network, Cpu, Lock, Sparkles,
} from 'lucide-react'
import { Card } from '../components/ui'
import { NetworkHero } from '../components/NetworkHero'

const FEATURES = [
  {
    icon: Users,
    color: 'var(--am-trader)',
    title: 'Six agents, one debate',
    body: 'A Market Analyst reads the regime, a Bull and a Bear argue it out, a Risk Manager sets the size envelope, and a Trader and Portfolio Manager land the decision.',
  },
  {
    icon: BrainCircuit,
    color: 'var(--am-reflect)',
    title: 'It reflects on every trade',
    body: 'Once an outcome is knowable, the Reflection Agent diagnoses why the debate did or didn’t work — and writes a generalised lesson. Win or loss is computed, never guessed.',
  },
  {
    icon: Layers,
    color: 'var(--am-consolidate)',
    title: 'It distils what it learns',
    body: 'The Consolidation Agent merges related lessons into higher-order rules, so knowledge compounds instead of piling up as noise.',
  },
  {
    icon: Search,
    color: 'var(--am-cyan)',
    title: 'Memory that understands meaning',
    body: 'Every trade, lesson and regime lives in Supermemory. Ask in your own words and semantic recall surfaces what matters — no keywords required.',
  },
  {
    icon: GitBranch,
    color: 'var(--am-pm)',
    title: 'Provably traceable',
    body: 'Every lesson traces by id to the trade that produced it, and to the later decision that cited it. The learning loop isn’t asserted — it’s a graph you can click.',
  },
  {
    icon: ShieldCheck,
    color: 'var(--am-risk)',
    title: 'Defence in depth',
    body: 'Hard risk limits live in code, not in a prompt. A hard concentration cap overrides the model every single time, whatever it argues.',
  },
]

const STACK = [
  { icon: Cpu, label: 'Local 768-dim ONNX embeddings' },
  { icon: Lock, label: 'Self-hosted, encrypted on-device' },
  { icon: Workflow, label: 'LangGraph multi-agent orchestration' },
  { icon: Network, label: 'Supermemory semantic layer' },
]

export function Overview() {
  return (
    <div>
      {/* ── Hero: copy on top, the living network below it ───────── */}
      <Card className="relative overflow-hidden mb-6" glow>
        <div className="px-6 sm:px-10 pt-12 text-center">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-2 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent"
          >
            <Sparkles size={12} /> AlphaMemoir
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.08 }}
            className="mx-auto mt-5 max-w-3xl text-4xl sm:text-[54px] font-bold leading-[1.05] tracking-tight text-text text-balance"
          >
            A living trading brain
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.16 }}
            className="mx-auto mt-4 max-w-xl text-base sm:text-lg leading-relaxed text-muted"
          >
            Six agents debate every trade. It reflects on what happened, distils the lesson,
            and remembers — so the next decision is made by an agent that has already learned.
            <span className="text-text font-medium"> It gets better with time.</span>
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.24 }}
            className="mt-7 flex flex-wrap items-center justify-center gap-3"
          >
            <Link
              to="/orchestration"
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-accent-contrast hover:bg-accent-hover transition-colors"
              style={{ boxShadow: '0 10px 30px -12px var(--glow)' }}
            >
              <Workflow size={16} /> Watch the agents think
            </Link>
            <Link
              to="/memory"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface-2 px-5 py-2.5 text-sm font-semibold text-text hover:border-accent transition-colors"
            >
              <Network size={16} /> Explore the memory
            </Link>
          </motion.div>
        </div>

        {/* the living memory network — interactive */}
        <div className="mt-8 -mb-1">
          <NetworkHero height={340} />
        </div>
        <p className="pb-5 text-center text-xs text-faint">Move your cursor through the network — it responds ↑</p>
      </Card>

      {/* ── What it does ─────────────────────────────────────────── */}
      <div className="mb-2 flex items-end justify-between">
        <h2 className="text-lg font-bold tracking-tight text-text">What makes it different</h2>
        <span className="text-xs text-faint">every claim on this page is live in the app</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.05 * i }}
          >
            <Card className="p-5 h-full hover:border-accent transition-colors">
              <span
                className="grid h-10 w-10 place-items-center rounded-xl mb-3"
                style={{ background: `color-mix(in srgb, ${f.color} 16%, transparent)` }}
              >
                <f.icon size={19} style={{ color: f.color }} />
              </span>
              <h3 className="text-[15px] font-semibold text-text">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.body}</p>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* ── The loop ─────────────────────────────────────────────── */}
      <Card className="p-6 mt-6">
        <h2 className="text-lg font-bold tracking-tight text-text">The loop that closes</h2>
        <p className="mt-1 text-sm text-muted">Most trading bots are stateless. This one remembers, and the memory feeds straight back into the next decision.</p>
        <div className="mt-5 flex flex-wrap items-stretch gap-2">
          {[
            { icon: Users, label: 'Debate', desc: 'six agents reason', color: 'var(--am-trader)' },
            { icon: BrainCircuit, label: 'Reflect', desc: 'diagnose the outcome', color: 'var(--am-reflect)' },
            { icon: Layers, label: 'Consolidate', desc: 'distil the rule', color: 'var(--am-consolidate)' },
            { icon: Search, label: 'Recall', desc: 'shape the next trade', color: 'var(--am-cyan)' },
          ].map((s, i, arr) => (
            <div key={s.label} className="flex items-center gap-2 flex-1 min-w-[150px]">
              <div className="flex-1 rounded-xl border border-border bg-surface-2 p-4">
                <span className="grid h-9 w-9 place-items-center rounded-lg mb-2.5" style={{ background: `color-mix(in srgb, ${s.color} 16%, transparent)` }}>
                  <s.icon size={17} style={{ color: s.color }} />
                </span>
                <div className="text-sm font-semibold text-text">{s.label}</div>
                <div className="text-xs text-muted mt-0.5">{s.desc}</div>
              </div>
              {i < arr.length - 1 && <ArrowRight size={16} className="text-faint shrink-0" />}
            </div>
          ))}
        </div>
        <Link to="/memory" className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-accent hover:text-accent-hover">
          Reflect &amp; consolidate the memory yourself <ArrowRight size={15} />
        </Link>
      </Card>

      {/* ── Stack ────────────────────────────────────────────────── */}
      <Card className="p-5 mt-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {STACK.map((s) => (
            <div key={s.label} className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-surface-2 shrink-0">
                <s.icon size={15} className="text-accent" />
              </span>
              <span className="text-xs font-medium leading-snug text-muted">{s.label}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
