import '@xyflow/react/dist/style.css'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
} from '@xyflow/react'
import { Skeleton } from '@/components/ui/skeleton'
import { useDiscoverFields } from '@/hooks/queries/useDiscoverFields'
import { useQualysSchema } from '@/hooks/queries/useQualysSchema'
import { SourcePanelNode } from './SourcePanelNode'
import { TargetPanelNode } from './TargetPanelNode'
import { MappingEdge } from './MappingEdge'
import { DashedConnectionLine } from './DashedConnectionLine'
import type { SourcePanelData, TargetPanelData } from '@/types/canvas'

// nodeTypes and edgeTypes MUST be defined at module level — not inside component
// (React Flow re-renders without flickering when these are stable references)
const nodeTypes = {
  sourcePanel: SourcePanelNode,
  targetPanel: TargetPanelNode,
}

const edgeTypes = {
  mapping: MappingEdge,
}

// Pure helper for onConnect — exported for unit testing
export function applyConnect(connection: Connection, currentEdges: Edge[]): Edge[] {
  // Replace any existing edge from this source OR to this target (one-to-one enforcement)
  const filtered = currentEdges.filter(
    e => e.source !== connection.source && e.target !== connection.target
  )
  return addEdge(
    { ...connection, type: 'mapping', data: { mappingType: 'direct' } },
    filtered
  )
}

// Pure helper for isValidConnection — exported for unit testing
// Accepts Connection | Edge per IsValidConnection<Edge> constraint
export function isValidConnection(connection: Connection | Edge): boolean {
  // Only block self-loops; onConnect handles replacement for duplicate source/target
  return connection.source !== connection.target
}

interface MappingCanvasProps {
  connectorId: string
}

export function MappingCanvas({ connectorId }: MappingCanvasProps) {
  const { data: discoverData, isLoading: loadingFields, isError: fieldsError } = useDiscoverFields(connectorId)
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
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => applyConnect(connection, eds))
    },
    [setEdges]
  )

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

  if (fieldsError) {
    return (
      <div className="w-full h-full flex items-center justify-center text-center text-muted-foreground p-8">
        <div>
          <p className="font-medium">Could not discover source fields</p>
          <p className="text-sm mt-1">
            The connector's source API is unreachable. Verify the connector's base URL and credentials are correct, then try again.
          </p>
        </div>
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
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        connectionLineComponent={DashedConnectionLine}
        defaultEdgeOptions={{ type: 'mapping' }}
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
