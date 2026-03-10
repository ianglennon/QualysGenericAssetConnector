import '@xyflow/react/dist/style.css'
import { useEffect, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import { Skeleton } from '@/components/ui/skeleton'
import { useDiscoverFields } from '@/hooks/queries/useDiscoverFields'
import { useQualysSchema } from '@/hooks/queries/useQualysSchema'
import { SourcePanelNode } from './SourcePanelNode'
import { TargetPanelNode } from './TargetPanelNode'
import type { SourcePanelData, TargetPanelData } from '@/types/canvas'

// nodeTypes and edgeTypes MUST be defined at module level — not inside component
// (React Flow re-renders without flickering when these are stable references)
const nodeTypes = {
  sourcePanel: SourcePanelNode,
  targetPanel: TargetPanelNode,
}

const edgeTypes = {} // MappingEdge added in Plan 03

interface MappingCanvasProps {
  connectorId: string
}

export function MappingCanvas({ connectorId }: MappingCanvasProps) {
  const { data: discoverData, isLoading: loadingFields } = useDiscoverFields(connectorId)
  const { data: schemaData, isLoading: loadingSchema } = useQualysSchema()

  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(800)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    setContainerWidth(el.offsetWidth)
    const ro = new ResizeObserver(entries => setContainerWidth(entries[0].contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const SOURCE_WIDTH = Math.floor(containerWidth * 0.35)
  const TARGET_WIDTH = Math.floor(containerWidth * 0.35)
  const TARGET_X = containerWidth - TARGET_WIDTH

  const initialNodes: Node[] = [
    {
      id: 'source-panel',
      type: 'sourcePanel',
      position: { x: 0, y: 0 },
      data: { fields: [], linkedSourceFields: new Set() } satisfies SourcePanelData,
      draggable: false,
      selectable: false,
      style: { width: SOURCE_WIDTH, height: 520 },
    },
    {
      id: 'target-panel',
      type: 'targetPanel',
      position: { x: TARGET_X, y: 0 },
      data: { fields: [], linkedTargetFields: new Set() } satisfies TargetPanelData,
      draggable: false,
      selectable: false,
      style: { width: TARGET_WIDTH, height: 520 },
    },
  ]

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, , onEdgesChange] = useEdgesState<Edge>([])

  // Update node widths when container resizes
  useEffect(() => {
    setNodes(nds =>
      nds.map(n => {
        if (n.id === 'source-panel') {
          return { ...n, position: { x: 0, y: 0 }, style: { ...n.style, width: SOURCE_WIDTH } }
        }
        if (n.id === 'target-panel') {
          return { ...n, position: { x: TARGET_X, y: 0 }, style: { ...n.style, width: TARGET_WIDTH } }
        }
        return n
      })
    )
  }, [SOURCE_WIDTH, TARGET_WIDTH, TARGET_X, setNodes])

  // Update source panel data when fields arrive
  useEffect(() => {
    const fields = discoverData?.fields ?? []
    const linkedSourceFields = new Set(
      edges.filter(e => e.sourceHandle).map(e => e.sourceHandle as string)
    )
    setNodes(nds =>
      nds.map(n =>
        n.id === 'source-panel'
          ? { ...n, data: { fields, linkedSourceFields } satisfies SourcePanelData }
          : n
      )
    )
  }, [discoverData, edges, setNodes])

  // Update target panel data when schema arrives
  useEffect(() => {
    const fields = schemaData?.fields ?? []
    const linkedTargetFields = new Set(
      edges.filter(e => e.targetHandle).map(e => e.targetHandle as string)
    )
    setNodes(nds =>
      nds.map(n =>
        n.id === 'target-panel'
          ? { ...n, data: { fields, linkedTargetFields } satisfies TargetPanelData }
          : n
      )
    )
  }, [schemaData, edges, setNodes])

  if (loadingFields || loadingSchema) {
    return (
      <div className="w-full h-full flex gap-4 p-4">
        <Skeleton className="flex-1 h-full rounded-lg" />
        <Skeleton className="w-32 h-full rounded-lg" />
        <Skeleton className="flex-1 h-full rounded-lg" />
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        panOnDrag={false}
        panOnScroll={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        nodesDraggable={false}
        nodesConnectable={true}
        elementsSelectable={false}
        preventScrolling={false}
        fitView={false}
        style={{ width: '100%', height: '100%' }}
      >
        <Background variant={BackgroundVariant.Dots} />
      </ReactFlow>
    </div>
  )
}
