import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Sidebar, SidebarRail } from './components/Sidebar'
import { Overview } from './pages/Overview'
import { Market } from './pages/Market'
import { MemoryExplorer } from './pages/MemoryExplorer'
import { Orchestration } from './pages/Orchestration'

export default function App() {
  // Collapsed by default: the dashboard is the point, the nav is not.
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className="min-h-screen">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      {!navOpen && <SidebarRail onOpen={() => setNavOpen(true)} />}

      {/* Closed, the content still leaves room for the floating rail so it can
          never sit on top of a page header. Open, it is pushed aside on lg+;
          below that the panel overlays instead and the padding stays put. */}
      <main
        className={`transition-[padding] duration-300 ease-out ${
          navOpen ? 'pl-[72px] lg:pl-[248px]' : 'pl-[72px]'
        }`}
      >
        <div className="mx-auto max-w-[1240px] px-6 md:px-8 py-8">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/market" element={<Market />} />
            <Route path="/memory" element={<MemoryExplorer />} />
            <Route path="/orchestration" element={<Orchestration />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}
