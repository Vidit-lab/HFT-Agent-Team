import { useMemo, useState, useCallback } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Cpu, BrainCircuit, Layers } from 'lucide-react'
import type { MemoryGraph } from '../lib/api'
import { tidyNumbers } from '../lib/format'

const KIND = {
  trade: { color: 'var(--am-trader)', icon: Cpu, label: 'Trade' },
  lesson: { color: 'var(--am-cyan)', icon: BrainCircuit, label: 'Lesson' },
  consolidated: { color: 'var(--am-consolidate)', icon: Layers, label: 'Meta-lesson' },
} as const

const EDGE = {
  reflected_from: { color: 'var(--am-reflect)', label: 'reflected into', animated: false },
  consolidated_into: { color: 'var(--am-consolidate)', label: 'consolidated into', animated: false },
  cited_by: { color: 'var(--am-cyan)', label: 'cited by later trade', animated: true },
} as const

type NodeData = { kind: keyof typeof KIND; label: string; regime: string | null; outcome: string | null; dim: boolean }

function GraphNode({ data }: NodeProps<Node<NodeData>>) {
  const meta = KIND[data.kind]
  const Icon = meta.icon
  return (
    <div
      className="rounded-xl border px-3 py-2.5 w-[220px] transition-opacity"
      style={{
        background: 'var(--surface)',
        borderColor: meta.color,
        boxShadow: `0 0 0 1px ${meta.color}22, 0 8px 24px -14px ${meta.color}`,
        opacity: data.dim ? 0.28 : 1,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: meta.color, border: 'none', width: 7, height: 7 }} />
      <Handle type="source" position={Position.Right} style={{ background: meta.color, border: 'none', width: 7, height: 7 }} />
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="grid h-5 w-5 place-items-center rounded" style={{ background: `color-mix(in srgb, ${meta.color} 18%, transparent)` }}>
          <Icon size={12} style={{ color: meta.color }} />
        </span>
        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: meta.color }}>
          {meta.label}
        </span>
        {data.outcome && (
          <span className="ml-auto text-[10px] font-semibold" style={{ color: data.outcome === 'win' ? 'var(--am-gain)' : data.outcome === 'loss' ? 'var(--am-loss)' : 'var(--am-warn)' }}>
            {data.outcome}
          </span>
        )}
      </div>
      <div className="text-[11px] leading-snug text-text line-clamp-3">{tidyNumbers(data.label)}</div>
    </div>
  )
}

const nodeTypes = { mem: GraphNode }

export function ProvenanceGraph({ graph, height = 520 }: { graph: MemoryGraph; height?: number }) {
  const [selected, setSelected] = useState<string | null>(null)

  const { nodes, edges } = useMemo(() => {
    const columns: Record<string, number> = { trade: 40, lesson: 380, consolidated: 720 }
    const counters: Record<string, number> = { trade: 0, lesson: 0, consolidated: 0 }
    const perCol: Record<string, number> = {}
    graph.nodes.forEach((n) => (perCol[n.kind] = (perCol[n.kind] ?? 0) + 1))

    const connected = new Set<string>()
    if (selected) {
      connected.add(selected)
      graph.edges.forEach((e) => {
        if (e.source === selected) connected.add(e.target)
        if (e.target === selected) connected.add(e.source)
      })
    }

    const nodes: Node<NodeData>[] = graph.nodes.map((n) => {
      const i = counters[n.kind]++
      const total = perCol[n.kind]
      const y = i * 110 - ((total - 1) * 110) / 2 + 300
      return {
        id: n.id,
        type: 'mem',
        position: { x: columns[n.kind] ?? 400, y },
        data: {
          kind: n.kind,
          label: n.label,
          regime: n.regime,
          outcome: n.outcome,
          dim: selected != null && !connected.has(n.id),
        },
      }
    })

    const edges: Edge[] = graph.edges.map((e, idx) => {
      const meta = EDGE[e.kind]
      const active = !selected || e.source === selected || e.target === selected
      return {
        id: `e${idx}`,
        source: e.source,
        target: e.target,
        animated: meta.animated && active,
        style: { stroke: meta.color, strokeWidth: active ? 2 : 1, opacity: active ? 0.9 : 0.15 },
        markerEnd: { type: MarkerType.ArrowClosed, color: meta.color, width: 14, height: 14 },
      }
    })

    return { nodes, edges }
  }, [graph, selected])

  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelected((s) => (s === node.id ? null : node.id))
  }, [])

  // `fitView` only runs on mount, so remount whenever the graph actually grows
  // (a reflect/consolidate adds nodes) -- otherwise new nodes render off-screen.
  const fitKey = `${graph.nodes.length}-${graph.edges.length}`

  return (
    <div style={{ height }} className="rounded-xl overflow-hidden border border-border">
      <ReactFlow
        key={fitKey}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        onPaneClick={() => setSelected(null)}
        fitView
        fitViewOptions={{ padding: 0.16 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="var(--border)" />
      </ReactFlow>
    </div>
  )
}
