import { NavLink } from 'react-router-dom'
import { LayoutDashboard, CandlestickChart, Network, Workflow, Moon, Sun, BrainCircuit } from 'lucide-react'
import { useTheme } from '../lib/theme'
import { useHealth } from '../lib/hooks'

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/orchestration', label: 'Live Orchestration', icon: Workflow },
  { to: '/memory', label: 'Memory Explorer', icon: Network, star: true },
  { to: '/market', label: 'Market & Ledger', icon: CandlestickChart },
]

export function Sidebar() {
  const { theme, toggle } = useTheme()
  const online = useHealth()

  return (
    <aside className="fixed inset-y-0 left-0 w-[248px] border-r border-border bg-surface/70 backdrop-blur-xl flex flex-col z-20">
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-2.5">
          <div
            className="grid h-9 w-9 place-items-center rounded-xl"
            style={{ background: 'linear-gradient(135deg, var(--am-blue), var(--am-cyan))', boxShadow: '0 6px 18px -6px var(--glow)' }}
          >
            <BrainCircuit size={20} className="text-white" strokeWidth={2.2} />
          </div>
          <div className="leading-tight">
            <div className="font-bold text-[15px] tracking-tight text-text">AlphaMemoir</div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-faint">Memory-Native Trading</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {nav.map(({ to, label, icon: Icon, end, star }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive ? 'text-accent-contrast' : 'text-muted hover:text-text hover:bg-surface-2'
              }`
            }
            style={({ isActive }: { isActive: boolean }) =>
              isActive
                ? { background: 'linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--am-cyan) 55%, var(--accent)))', boxShadow: '0 8px 20px -10px var(--glow)' }
                : undefined
            }
          >
            <Icon size={18} strokeWidth={2} />
            <span className="flex-1">{label}</span>
            {star && <span className="h-1.5 w-1.5 rounded-full bg-cyan" style={{ boxShadow: '0 0 8px var(--am-cyan)' }} />}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 space-y-2 border-t border-border">
        <div className="flex items-center justify-between px-2 py-1.5 text-xs">
          <span className="flex items-center gap-2 text-muted">
            <span className={`h-2 w-2 rounded-full ${online ? 'bg-gain' : 'bg-loss'}`} style={online ? { boxShadow: '0 0 8px var(--am-gain)' } : undefined} />
            {online ? 'API connected' : 'API offline'}
          </span>
        </div>
        <button
          onClick={toggle}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted hover:text-text hover:bg-surface-2 transition-colors"
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  )
}
