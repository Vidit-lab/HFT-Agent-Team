import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

/** Every query that a write can invalidate.
 *
 *  Kept in one place on purpose. A cycle doesn't just add a trade -- it also
 *  writes a trade memory and a regime snapshot into Supermemory, so the Memory
 *  Explorer goes stale too. Reflecting adds a lesson AND changes what is pending
 *  AND grows the provenance graph. Anything that lists these keys by hand drifts
 *  out of date the moment a new panel is added, and the symptom is the worst
 *  kind: the system did the work, and the UI quietly showed yesterday's answer.
 */
const LEDGER_KEYS = ['portfolio', 'trades', 'ohlcv'] as const
const MEMORY_KEYS = [
  'stats',
  'documents',
  'graph',
  'reflections',
  'consolidations',
  'pending-reflection',
  'pending-consolidation',
] as const

export function useRefreshAll() {
  const qc = useQueryClient()
  return useCallback(() => {
    for (const key of [...LEDGER_KEYS, ...MEMORY_KEYS]) {
      qc.invalidateQueries({ queryKey: [key] })
    }
  }, [qc])
}

/** The memory is a living store, not a page load.
 *
 *  A cycle, a reflect or a consolidate can be driven from another tab, another
 *  client, or a script -- and Supermemory also indexes asynchronously, so a
 *  document can land a second or two *after* the write returns. Without a poll,
 *  an open Memory Explorer is a photograph: the sell gets stored, the graph edge
 *  forms, and the page keeps showing the moment before it happened.
 *
 *  Every one of these is a cheap local read (SQLite, or Supermemory on
 *  localhost), so a 10s poll costs nothing and the section stays true.
 */
const LIVE = { refetchInterval: 10_000 } as const

export const useStats = () => useQuery({ queryKey: ['stats'], queryFn: api.memoryStats, ...LIVE })
export const usePortfolio = () => useQuery({ queryKey: ['portfolio'], queryFn: () => api.portfolio(), ...LIVE })
export const useTrades = () => useQuery({ queryKey: ['trades'], queryFn: () => api.trades(), ...LIVE })
// The two polls that make the chart feel alive. Both are TTL-cached server-side
// (20s bars / 5s ticker), so extra tabs cost the exchange nothing.
export const useOHLCV = (symbol: string, timeframe: string) =>
  useQuery({
    queryKey: ['ohlcv', symbol, timeframe],
    queryFn: () => api.ohlcv(symbol, timeframe),
    refetchInterval: 20_000,
    placeholderData: (prev) => prev, // keep the old candles on screen while the new ones land
  })

export const useQuote = (symbol: string) =>
  useQuery({
    queryKey: ['quote', symbol],
    queryFn: () => api.quote(symbol),
    refetchInterval: 5_000,
    placeholderData: (prev) => prev,
  })
export const useDocuments = (type?: string) =>
  useQuery({ queryKey: ['documents', type ?? 'all'], queryFn: () => api.memoryDocuments(type), ...LIVE })
export const useGraph = () => useQuery({ queryKey: ['graph'], queryFn: api.memoryGraph, ...LIVE })
export const useReflections = () => useQuery({ queryKey: ['reflections'], queryFn: api.reflections, ...LIVE })
export const useConsolidations = () =>
  useQuery({ queryKey: ['consolidations'], queryFn: api.consolidations, ...LIVE })

export const usePendingReflection = (lookbackDays: number) =>
  useQuery({
    queryKey: ['pending-reflection', lookbackDays],
    queryFn: () => api.pendingReflection(lookbackDays),
    ...LIVE,
  })
export const usePendingConsolidation = () =>
  useQuery({ queryKey: ['pending-consolidation'], queryFn: api.pendingConsolidation, ...LIVE })

export function useHealth() {
  const [online, setOnline] = useState(false)
  useEffect(() => {
    let alive = true
    const check = () =>
      fetch('/api/memory/stats')
        .then((r) => alive && setOnline(r.ok))
        .catch(() => alive && setOnline(false))
    check()
    const t = setInterval(check, 15000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])
  return online
}
