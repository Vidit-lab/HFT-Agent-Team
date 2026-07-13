import { useEffect, useRef } from 'react'
import { useTheme } from '../lib/theme'

type Node = { x: number; y: number; vx: number; vy: number; r: number; label?: string; pulse: number }

const LABELS = ['trade', 'lesson', 'meta-lesson', 'regime', 'recall', 'reflect']
const LINK_DIST = 132
const MOUSE_DIST = 150

function cssVar(name: string, fallback: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

/** The living-memory constellation. Nodes drift; nearby ones link up; the cursor
 *  pulls the network toward it and lights up whatever it touches. Purely
 *  decorative — but it's the project's thesis made tangible: a web of memories
 *  that connect. */
export function NetworkHero({ height = 380 }: { height?: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const { theme } = useTheme()

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const blue = cssVar('--am-blue', '#0983C8')
    const cyan = cssVar('--am-cyan', '#5ACAF9')
    const line = theme === 'dark' ? 'rgba(90,202,249,' : 'rgba(9,131,200,'
    const labelBg = theme === 'dark' ? '#0d2f52' : '#e7f1f9'
    const labelFg = theme === 'dark' ? '#BADEEF' : '#0a4a75'

    let w = 0
    let h = 0
    let raf = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const mouse = { x: -9999, y: -9999 }
    let nodes: Node[] = []

    const build = () => {
      const count = Math.round(Math.min(64, Math.max(30, w / 20)))
      nodes = Array.from({ length: count }, (_, i) => ({
        x: Math.random() * w,
        // bias toward the vertical middle so it reads as a band, like the reference
        y: h * 0.16 + Math.random() * h * 0.68,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: 2 + Math.random() * 4.5,
        label: i < LABELS.length ? LABELS[i] : undefined,
        pulse: Math.random() * Math.PI * 2,
      }))
      // labelled nodes are the hubs — bigger
      nodes.slice(0, LABELS.length).forEach((n) => (n.r = 5.5 + Math.random() * 2))
    }

    const resize = () => {
      w = canvas.clientWidth
      h = canvas.clientHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      build()
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h)

      // edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i]
          const b = nodes[j]
          const d = Math.hypot(a.x - b.x, a.y - b.y)
          if (d < LINK_DIST) {
            ctx.strokeStyle = `${line}${(1 - d / LINK_DIST) * 0.5})`
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.stroke()
          }
        }
      }

      // cursor links
      for (const n of nodes) {
        const d = Math.hypot(n.x - mouse.x, n.y - mouse.y)
        if (d < MOUSE_DIST) {
          ctx.strokeStyle = `${line}${(1 - d / MOUSE_DIST) * 0.85})`
          ctx.lineWidth = 1.2
          ctx.beginPath()
          ctx.moveTo(n.x, n.y)
          ctx.lineTo(mouse.x, mouse.y)
          ctx.stroke()
        }
      }

      // nodes
      for (const n of nodes) {
        const d = Math.hypot(n.x - mouse.x, n.y - mouse.y)
        const near = d < MOUSE_DIST ? 1 - d / MOUSE_DIST : 0
        const breathe = reduced ? 0 : Math.sin(n.pulse) * 0.5
        const r = n.r + near * 3 + breathe

        ctx.save()
        ctx.shadowBlur = 10 + near * 18
        ctx.shadowColor = cyan
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, Math.max(r, 0.5))
        grad.addColorStop(0, cyan)
        grad.addColorStop(1, blue)
        ctx.fillStyle = grad
        ctx.globalAlpha = 0.55 + near * 0.45
        ctx.beginPath()
        ctx.arc(n.x, n.y, Math.max(r, 0.5), 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()

        // hub ring
        if (n.label) {
          ctx.strokeStyle = `${line}${0.5 + near * 0.5})`
          ctx.lineWidth = 1.4
          ctx.beginPath()
          ctx.arc(n.x, n.y, r + 5, 0, Math.PI * 2)
          ctx.stroke()

          // label pill
          ctx.font = '600 10px "Inter Variable", sans-serif'
          const tw = ctx.measureText(n.label).width
          const px = n.x + r + 10
          const py = n.y - 8
          ctx.globalAlpha = 0.9
          ctx.fillStyle = labelBg
          ctx.beginPath()
          ctx.roundRect(px, py, tw + 14, 17, 5)
          ctx.fill()
          ctx.strokeStyle = `${line}0.45)`
          ctx.lineWidth = 1
          ctx.stroke()
          ctx.fillStyle = labelFg
          ctx.fillText(n.label, px + 7, py + 12)
          ctx.globalAlpha = 1
        }
      }
    }

    const step = () => {
      for (const n of nodes) {
        if (!reduced) {
          n.x += n.vx
          n.y += n.vy
          n.pulse += 0.02
          // drift back inside
          if (n.x < 0 || n.x > w) n.vx *= -1
          if (n.y < h * 0.08 || n.y > h * 0.92) n.vy *= -1
          // gentle pull toward the cursor
          const d = Math.hypot(n.x - mouse.x, n.y - mouse.y)
          if (d < MOUSE_DIST && d > 1) {
            n.x += ((mouse.x - n.x) / d) * 0.35
            n.y += ((mouse.y - n.y) / d) * 0.35
          }
        }
      }
      draw()
      raf = requestAnimationFrame(step)
    }

    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mouse.x = e.clientX - rect.left
      mouse.y = e.clientY - rect.top
    }
    const onLeave = () => {
      mouse.x = -9999
      mouse.y = -9999
    }

    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    canvas.addEventListener('mousemove', onMove)
    canvas.addEventListener('mouseleave', onLeave)
    step()

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      canvas.removeEventListener('mousemove', onMove)
      canvas.removeEventListener('mouseleave', onLeave)
    }
  }, [theme])

  return <canvas ref={ref} style={{ width: '100%', height, display: 'block', cursor: 'crosshair' }} aria-hidden="true" />
}
