import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type CandlestickData,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'
import type { OHLCVBar, TradeMarker } from '../lib/api'
import { useTheme } from '../lib/theme'

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

// lightweight-charts renders a UTCTimestamp in UTC. Left alone, a viewer in
// IST reads a 12:00 label at 17:30 on their own clock and concludes the feed is
// five hours stale -- when it is in fact the candle currently forming. So we
// format every axis tick and crosshair label in the viewer's own timezone.
const localTime = (t: number) =>
  new Date(t * 1000).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })

const localDate = (t: number) =>
  new Date(t * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

export function PriceChart({
  bars,
  markers,
  intraday = true,
  height = 380,
}: {
  bars: OHLCVBar[]
  markers: TradeMarker[]
  intraday?: boolean
  height?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const fittedRef = useRef(false)
  const { theme } = useTheme()

  // Build the chart once per theme/geometry change -- NOT per data change. The
  // live feed repolls every 20s, and recreating the chart each time would blow
  // away the viewer's zoom and pan mid-look.
  useEffect(() => {
    if (!ref.current) return
    const el = ref.current

    const text = cssVar('--text-muted') || '#86a9c8'
    const grid = theme === 'dark' ? 'rgba(23,64,106,0.5)' : 'rgba(211,227,240,0.8)'
    const chart = createChart(el, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: text,
        fontFamily: "'Inter Variable', sans-serif",
        attributionLogo: false,
      },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      rightPriceScale: { borderColor: grid },
      timeScale: {
        borderColor: grid,
        timeVisible: intraday,
        secondsVisible: false,
        tickMarkFormatter: (time: Time, tickMarkType: number) => {
          const t = time as number
          // TickMarkType.Time === 3, TimeWithSeconds === 4; anything lower is a
          // date boundary (year/month/day) and should stay a date.
          return intraday && tickMarkType >= 3 ? localTime(t) : localDate(t)
        },
      },
      localization: {
        timeFormatter: (time: Time) => {
          const t = time as number
          return intraday ? `${localDate(t)} ${localTime(t)}` : localDate(t)
        },
      },
      crosshair: { mode: 0 },
    })

    const series = chart.addSeries(CandlestickSeries, {
      upColor: cssVar('--am-gain') || '#21c197',
      downColor: cssVar('--am-loss') || '#f0616d',
      borderUpColor: cssVar('--am-gain') || '#21c197',
      borderDownColor: cssVar('--am-loss') || '#f0616d',
      wickUpColor: cssVar('--am-gain') || '#21c197',
      wickDownColor: cssVar('--am-loss') || '#f0616d',
    })

    chartRef.current = chart
    seriesRef.current = series
    markersRef.current = createSeriesMarkers(series, [])
    fittedRef.current = false

    const ro = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }))
    ro.observe(el)
    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      markersRef.current = null
    }
  }, [height, theme, intraday])

  // Data updates flow into the existing series, so a repoll just slides the last
  // candle forward. fitContent runs only on the first load of a given series.
  useEffect(() => {
    const series = seriesRef.current
    if (!series || bars.length === 0) return

    series.setData(
      bars.map((b): CandlestickData<Time> => ({
        time: b.time as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    )

    const accent = cssVar('--accent') || '#159de0'
    markersRef.current?.setMarkers(
      markers.map((mk): SeriesMarker<Time> => ({
        time: mk.time as Time,
        position: mk.side === 'buy' ? 'belowBar' : 'aboveBar',
        color: accent,
        shape: mk.side === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${mk.side.toUpperCase()} #${mk.trade_id}`,
      })),
    )

    if (!fittedRef.current) {
      chartRef.current?.timeScale().fitContent()
      fittedRef.current = true
    }
  }, [bars, markers])

  return <div ref={ref} style={{ width: '100%' }} />
}
