import '@xyflow/react/dist/style.css'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { Button } from '@/components/ui/button'
import { useQualysSchema } from '@/hooks/queries/useQualysSchema'
import { useEndpointMappings } from '@/hooks/queries/useEndpointMappings'
import { useEndpointDiscoverFields } from '@/hooks/queries/useEndpointDiscover'
import { SourcePanelNode } from './SourcePanelNode'
import { TargetPanelNode } from './TargetPanelNode'
import { MappingEdge } from './MappingEdge'
import { DashedConnectionLine } from './DashedConnectionLine'
import type { SourcePanelData, TargetPanelData, MappingEdgeData, CanvasConditionRule, StaticValueType, DiscoverResponse } from '@/types/canvas'
import { apiTypeToCanvas } from '@/types/canvas'

// Helper: infer StaticValueType from a string value
function inferValueType(v: string | null | undefined): StaticValueType {
  if (v === 'true' || v === 'false') return 'boolean'
  if (v !== null && v !== undefined && v !== '' && !isNaN(Number(v))) return 'number'
  return 'string'
}

// nodeTypes and edgeTypes MUST be defined at module level — not inside component
// (React Flow re-renders without flickering when these are stable references)
const nodeTypes = {
  sourcePanel: SourcePanelNode,
  targetPanel: TargetPanelNode,
}

const edgeTypes = {
  mapping: MappingEdge,
}

// Normalize connection so source is always source-panel, target is always target-panel.
// React Flow may invert source/target depending on drag direction.
export function normalizeConnection(connection: Connection): Connection {
  if (connection.source === 'source-panel') return connection
  return {
    source: 'target-panel' === connection.source ? 'source-panel' : connection.source,
    target: 'source-panel' === connection.target ? 'target-panel' : connection.target,
    sourceHandle: connection.targetHandle,
    targetHandle: connection.sourceHandle,
  }
}

// Pure helper for onConnect — exported for unit testing
export function applyConnect(connection: Connection, currentEdges: Edge[]): Edge[] {
  const norm = normalizeConnection(connection)
  // One-to-one: each source field maps to one target, each target receives from one source
  const filtered = currentEdges.filter(
    e => e.sourceHandle !== norm.sourceHandle && e.targetHandle !== norm.targetHandle
  )
  return addEdge(
    { ...norm, type: 'mapping', data: { mappingType: 'direct' } },
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
  connectorId: string   // for page header + back navigation context
  endpointId: string    // used for all API calls
  onEdgesSnapshot?: (edges: Edge<MappingEdgeData>[]) => void
}

export function MappingCanvas({ connectorId, endpointId, onEdgesSnapshot }: MappingCanvasProps) {
  const { data: schemaData, isLoading: loadingSchema } = useQualysSchema()
  const { data: savedMappings, isLoading: loadingMappings, isError: mappingsError } = useEndpointMappings(connectorId, endpointId)
  const discoverFields = useEndpointDiscoverFields()
  const [discoveredFields, setDiscoveredFields] = useState<DiscoverResponse | null>(null)

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
      data: { fields: [], linkedSourceFields: new Set(), linkedFieldOrder: new Map() } satisfies SourcePanelData,
      draggable: false,
      selectable: false,
      style: { width: SOURCE_WIDTH, height: 520 },
    },
    {
      id: 'target-panel',
      type: 'targetPanel',
      position: { x: TARGET_X, y: 0 },
      data: { fields: [], linkedTargetFields: new Set(), linkedFieldOrder: new Map(), customAttributes: [] } satisfies TargetPanelData,
      draggable: false,
      selectable: false,
      style: { width: TARGET_WIDTH, height: 520 },
    },
  ]

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  const seededEndpointRef = useRef<string | null>(null)
  const prevEndpointRef = useRef(endpointId)

  // Reset when endpointId genuinely changes (NOT on initial mount — that
  // would race with the seed-edges effect below and clear freshly-seeded edges)
  useEffect(() => {
    if (prevEndpointRef.current === endpointId) return
    prevEndpointRef.current = endpointId
    seededEndpointRef.current = null
    setEdges([])
    setDiscoveredFields(null)
  }, [endpointId, setEdges])

  // Compute source fields: discovered (if non-empty) > saved mappings fallback > empty
  const sourceFields = useMemo(() => {
    if (discoveredFields && discoveredFields.fields.length > 0) return discoveredFields.fields
    if (savedMappings && savedMappings.length > 0) {
      const seen = new Set<string>()
      return savedMappings
        .filter(m => m.source_field && !seen.has(m.source_field) && seen.add(m.source_field))
        .map(m => ({ path: m.source_field!, type: 'string', sample_value: null }))
    }
    return []
  }, [discoveredFields, savedMappings])

  // Helper: compute linked-field sets and edge-index sort orders from an edge list.
  // Each edge at index i assigns position i to its source and target field,
  // so linked fields appear at matching vertical positions → straight lines.
  function computePanelData(edgeList: Edge[]) {
    const sLinked = new Set<string>()
    const sOrder = new Map<string, number>()
    const tLinked = new Set<string>()
    const tOrder = new Map<string, number>()
    edgeList.forEach((e, i) => {
      if (e.sourceHandle) { sLinked.add(e.sourceHandle); sOrder.set(e.sourceHandle, i) }
      if (e.targetHandle) { tLinked.add(e.targetHandle); tOrder.set(e.targetHandle, i) }
    })
    return { sLinked, sOrder, tLinked, tOrder }
  }

  // Seed edges from saved mappings.
  // Edges are set immediately — React Flow won't render them until handles exist.
  // Panel nodes call updateNodeInternals after their handles mount, which triggers
  // React Flow to resolve edge positions and make them visible.
  useEffect(() => {
    if (!savedMappings || seededEndpointRef.current === endpointId) return
    seededEndpointRef.current = endpointId

    const seededEdges: Edge<MappingEdgeData>[] = savedMappings.map((m, i) => ({
      id: `seeded-${m.id ?? i}`,
      source: 'source-panel',
      sourceHandle: m.source_field ?? '',
      target: 'target-panel',
      targetHandle: m.target_field,
      type: 'mapping',
      data: {
        mappingType: apiTypeToCanvas(m.mapping_type),
        staticValue: m.static_value ?? undefined,
        valueType: inferValueType(m.static_value),
        conditions: (m.conditions ?? []) as CanvasConditionRule[],
        fallback: m.fallback ?? undefined,
      } satisfies MappingEdgeData,
    }))

    setEdges(seededEdges)
  }, [savedMappings, endpointId, setEdges])

  // Update both panels' node data whenever edges, source fields, or schema change.
  useEffect(() => {
    const { sLinked, sOrder, tLinked, tOrder } = computePanelData(edges)
    const targetFields = schemaData?.fields ?? []

    setNodes(nds =>
      nds.map(n => {
        if (n.id === 'source-panel') {
          return {
            ...n,
            data: {
              fields: sourceFields,
              linkedSourceFields: sLinked,
              linkedFieldOrder: sOrder,
            } satisfies SourcePanelData,
          }
        }
        if (n.id === 'target-panel') {
          return {
            ...n,
            data: {
              fields: targetFields,
              linkedTargetFields: tLinked,
              linkedFieldOrder: tOrder,
              customAttributes: (n.data as TargetPanelData).customAttributes ?? [],
            } satisfies TargetPanelData,
          }
        }
        return n
      })
    )
  }, [edges, sourceFields, schemaData, setNodes])

  // Auto-discover removed: when saved mappings exist, sourceFields falls back
  // to the field names extracted from those mappings (line 146). Users can click
  // "Discover Fields" manually to get the full field metadata. This avoids a
  // race condition where a failing or slow discovery call left the canvas empty.

  // Notify parent of edge changes
  useEffect(() => {
    onEdgesSnapshot?.(edges as Edge<MappingEdgeData>[])
  }, [edges, onEdgesSnapshot])

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

  function handleDiscoverClick() {
    discoverFields.mutate(
      { connectorId, endpointId },
      { onSuccess: (data) => setDiscoveredFields(data) }
    )
  }

  if (loadingSchema || loadingMappings) {
    return (
      <div className="w-full h-full flex gap-4 p-4">
        <Skeleton className="flex-1 h-full rounded-lg" />
        <Skeleton className="w-32 h-full rounded-lg" />
        <Skeleton className="flex-1 h-full rounded-lg" />
      </div>
    )
  }

  if (mappingsError) {
    return (
      <div className="w-full h-full flex items-center justify-center text-destructive">
        <p>Failed to load saved mappings. Please refresh the page.</p>
      </div>
    )
  }

  return (
    <div className="w-full h-full flex flex-col">
      {/* Source panel header with Discover Fields button */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <span className="text-sm font-medium text-muted-foreground">Source Fields</span>
        <Button
          size="sm"
          variant="outline"
          onClick={handleDiscoverClick}
          disabled={discoverFields.isPending}
        >
          {discoverFields.isPending ? (
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              Discovering...
            </span>
          ) : (
            'Discover Fields'
          )}
        </Button>
      </div>

      {/* Empty state overlay when no fields and no discovery data */}
      {sourceFields.length === 0 && !discoverFields.isPending && (
        <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none" style={{ top: '3rem' }}>
          <div className="text-center text-muted-foreground p-8">
            <p className="font-medium">No source fields loaded</p>
            <p className="text-sm mt-1">Click Discover Fields to load source fields from this endpoint</p>
          </div>
        </div>
      )}

      <div ref={containerRef} className="flex-1 relative">
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
    </div>
  )
}
