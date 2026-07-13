import { useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, CandlestickChart, Network, Workflow,
  Moon, Sun, BrainCircuit, PanelLeft, PanelLeftClose,
} from 'lucide-react'
import { useTheme } from '../lib/theme'
import { useHealth } from '../lib/hooks'

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/orchestration', label: 'Live Orchestration', icon: Workflow },
  { to: '/memory', label: 'Memory Explorer', icon: Network, star: true },
  { to: '/market', label: 'Market & Ledger', icon: CandlestickChart },
]

/** The controls that must stay reachable while the sidebar is closed.
 *
 *  The theme switch lives in the sidebar footer, and the sidebar now starts
 *  collapsed -- so without this rail the only way to change theme would be to
 *  open a panel you were trying to keep shut. It is rendered only when the
 *  sidebar is closed, so the two copies of the switch are never both on screen.
 */
export function SidebarRail({ onOpen }: { onOpen: () => void }) {
  const { theme, toggle } = useTheme()

  return (
    <div className="fixed left-3 top-4 z-40 flex flex-col gap-2">
      <button
        onClick={onOpen}
        aria-label="Open navigation"
        aria-expanded={false}
        className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-surface/80 text-muted backdrop-blur-xl transition-colors hover:border-accent hover:text-text"
      >
        <PanelLeft size={18} />
      </button>
      <button
        onClick={toggle}
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-surface/80 text-muted backdrop-blur-xl transition-colors hover:border-accent hover:text-text"
      >
        {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
      </button>
    </div>
  )
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { theme, toggle } = useTheme()
  const online = useHealth()

  // Escape closes it -- a panel you can open with one click should not need a
  // hunt for the close button.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <>
      {/* On narrow screens the panel overlays the content, so it needs a scrim.
          On lg+ it pushes the content instead and no scrim is wanted. */}
      {open && (
        <div
          onClick={onClose}
          aria-hidden
          className="fixed inset-0 z-20 bg-black/40 backdrop-blur-[2px] lg:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[248px] flex-col border-r border-border bg-surface/80 backdrop-blur-xl transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* The close button is absolute, not a flex sibling: at 248px wide the
            wordmark needs every pixel, and letting the button claim layout width
            wraps "Memory-Native Trading" onto a second line. */}
        <button
          onClick={onClose}
          aria-label="Close navigation"
          aria-expanded
          className="absolute right-2.5 top-4 z-10 grid h-8 w-8 place-items-center rounded-lg text-faint transition-colors hover:bg-surface-2 hover:text-text"
        >
          <PanelLeftClose size={17} />
        </button>

        <div className="px-5 pt-6 pb-5">
          <div className="flex items-center gap-2.5">
            <div
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl"
              style={{ background: 'linear-gradient(135deg, var(--am-blue), var(--am-cyan))', boxShadow: '0 6px 18px -6px var(--glow)' }}
            >
              <BrainCircuit size={20} className="text-white" strokeWidth={2.2} />
            </div>
            <div className="leading-tight">
              <div className="font-bold text-[15px] tracking-tight text-text">AlphaMemoir</div>
              <div className="whitespace-nowrap text-[9px] uppercase tracking-[0.18em] text-faint">Memory-Native Trading</div>
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
    </>
  )
}
