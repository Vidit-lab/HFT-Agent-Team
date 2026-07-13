export const fmtMoney = (n: number, digits = 2) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits })

export const fmtNum = (n: number, digits = 2) =>
  n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const fmtPct = (n: number, digits = 2) => `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`

export const fmtDate = (s: string) => {
  const d = new Date(s)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export const fmtDateTime = (s: string) => {
  const d = new Date(s)
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** "just now" / "12s ago" / "4m ago" -- the freshness line under the live price. */
export const fmtAgo = (iso: string) => {
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (secs < 5) return 'just now'
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
}

/** A bar's UNIX time as a local wall-clock label, e.g. "17:30". The chart axis is
 *  rendered in the viewer's timezone, so this must match it -- never UTC. */
export const fmtBarTime = (unixSecs: number) =>
  new Date(unixSecs * 1000).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })

/** Compact volume: 881136084 -> "$881.1M". */
export const fmtCompact = (n: number) =>
  `$${n.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 1 })}`

export const titleCase = (s: string) =>
  s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const shortId = (id: string) => (id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-3)}` : id)

/** Round every long decimal inside a text blob to 2dp. Memory content and agent
 *  rationales were written with raw float precision (e.g. "buy 79.2845345024189
 *  AAPL @ 315.47766732788085"), which reads as noise in the UI. Only touches
 *  numbers with 3+ decimal places, so ids, years and tidy figures are untouched. */
export const tidyNumbers = (text: string) =>
  text.replace(/\d+\.\d{3,}/g, (m) => Number(m).toFixed(2))
