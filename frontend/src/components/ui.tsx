import type { ReactNode } from 'react'

/* ── Layout primitives ─────────────────────────────────────────────── */

export function Card({ children, className = '', glow = false }: { children: ReactNode; className?: string; glow?: boolean }) {
  return (
    <div
      className={`am-card ${className}`}
      style={glow ? { boxShadow: '0 0 0 1px var(--border), 0 12px 40px -18px var(--glow)' } : undefined}
    >
      {children}
    </div>
  )
}

export function PageHeader({ eyebrow, title, sub, right }: { eyebrow?: string; title: string; sub?: string; right?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        {eyebrow && <div className="text-xs font-semibold uppercase tracking-[0.18em] text-accent mb-1.5">{eyebrow}</div>}
        <h1 className="text-2xl md:text-[28px] font-bold tracking-tight text-text text-balance">{title}</h1>
        {sub && <p className="text-sm text-muted mt-1.5 max-w-2xl">{sub}</p>}
      </div>
      {right}
    </header>
  )
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-muted">{children}</h2>
      {hint && <div className="text-xs text-faint">{hint}</div>}
    </div>
  )
}

/* ── Stat tile ─────────────────────────────────────────────────────── */

export function StatTile({
  label,
  value,
  sub,
  accent,
  icon,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  accent?: 'gain' | 'loss' | 'accent' | 'warn'
  icon?: ReactNode
}) {
  const color =
    accent === 'gain' ? 'text-gain' : accent === 'loss' ? 'text-loss' : accent === 'warn' ? 'text-warn' : 'text-text'
  return (
    <Card className="p-4 flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-faint">{label}</span>
        {icon && <span className="text-accent opacity-80">{icon}</span>}
      </div>
      <div className={`text-2xl font-bold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </Card>
  )
}

/* ── Pills / badges ────────────────────────────────────────────────── */

export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'gain' | 'loss' | 'warn' | 'accent' }) {
  const tones: Record<string, string> = {
    neutral: 'bg-surface-3 text-muted border-border',
    gain: 'text-gain border-transparent',
    loss: 'text-loss border-transparent',
    warn: 'text-warn border-transparent',
    accent: 'text-accent border-transparent',
  }
  const bg: Record<string, string | undefined> = {
    gain: 'color-mix(in srgb, var(--am-gain) 14%, transparent)',
    loss: 'color-mix(in srgb, var(--am-loss) 14%, transparent)',
    warn: 'color-mix(in srgb, var(--am-warn) 14%, transparent)',
    accent: 'color-mix(in srgb, var(--accent) 14%, transparent)',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}
      style={bg[tone] ? { backgroundColor: bg[tone] } : undefined}
    >
      {children}
    </span>
  )
}

export function OutcomeBadge({ outcome }: { outcome: string | null | undefined }) {
  if (!outcome) return <Pill>—</Pill>
  const tone = outcome === 'win' ? 'gain' : outcome === 'loss' ? 'loss' : 'warn'
  return <Pill tone={tone}>{outcome}</Pill>
}

export function RegimeBadge({ regime }: { regime: string | null | undefined }) {
  if (!regime) return null
  const dot =
    regime.includes('up') ? 'var(--am-gain)' : regime.includes('down') ? 'var(--am-loss)' : regime.includes('vol') ? 'var(--am-warn)' : 'var(--am-cyan)'
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
      <span className="h-2 w-2 rounded-full" style={{ background: dot, boxShadow: `0 0 8px ${dot}` }} />
      {regime.replace(/_/g, ' ')}
    </span>
  )
}

export function ActionBadge({ action }: { action: string }) {
  const tone = action === 'buy' ? 'gain' : action === 'sell' ? 'loss' : 'neutral'
  return <Pill tone={tone}>{action.toUpperCase()}</Pill>
}

/* ── States ────────────────────────────────────────────────────────── */

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surface-3 ${className}`} />
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center">
      <div className="text-sm font-medium text-muted">{title}</div>
      {hint && <div className="text-xs text-faint mt-1 max-w-sm">{hint}</div>}
    </div>
  )
}

export function ErrorState({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center">
      <div className="text-sm font-medium text-loss">Couldn’t load this data</div>
      <div className="text-xs text-faint mt-1 font-mono">{msg}</div>
      <div className="text-xs text-faint mt-2">Is the API running on :8000?</div>
    </div>
  )
}
