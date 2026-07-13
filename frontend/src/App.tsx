import { Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Overview } from './pages/Overview'
import { Market } from './pages/Market'
import { MemoryExplorer } from './pages/MemoryExplorer'
import { Orchestration } from './pages/Orchestration'

export default function App() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <main className="pl-[248px]">
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
