import '@xyflow/react/dist/style.css'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type Node,
  type OnConnectEnd,
} from '@xyflow/react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'
import { useQualysSchema } from '@/hooks/queries/useQualysSchema'
import { useCanvases, useCreateCanvas } from '@/hooks/queries/useCanvases'
import {
  useCanvasEndpoints,
  useCreateCanvasEndpoint,
  useUpdateCanvasEndpoint,
} from '@/hooks/queries/useCanvasEndpoints'
import { useCreateEndpoint } from '@/hooks/queries/useEndpoints'
import { useEndpointDiscoverFields } from '@/hooks/queries/useEndpointDiscover'
import { useBatchReplaceEndpointMappings } from '@/hooks/queries/useEndpointMappings'
import { EndpointNode } from './EndpointNode'
import { ChainEdge } from './ChainEdge'
import { MappingEdge } from '@/components/mappings/MappingCanvas/MappingEdge'
import { TargetPanelNode } from '@/components/mappings/MappingCanvas/TargetPanelNode'
import { DashedConnectionLine } from '@/components/mappings/MappingCanvas/DashedConnectionLine'
import { CanvasContextMenu } from './CanvasContextMenu'
import { CanvasToolbar } from './CanvasToolbar'
import { wouldCreateCycle } from './cycle-detection'
import { getLayoutedPositions } from './dagre-layout'
import type {
  EndpointNodeData,
  ChainEdgeData,
  MappingEdgeData,
  FieldDiscoveryItem,
  TargetPanelData,
} from '@/types/canvas'

// Module-level constants prevent React Flow re-render flickering (Pitfall 1)
const nodeTypes = {
  endpointNode: EndpointNode,
  targetPanel: TargetPanelNode,
}

const edgeTypes = {
  chain: ChainEdge,
  mapping: MappingEdge,
}

interface ChainCanvasProps {
  connectorId: string
  connectorName: string
}

const TARGET_PANEL_ID = 'target-panel'

function ChainCanvasInner({ connectorId, connectorName }: ChainCanvasProps) {
  const { toast } = useToast()
  const { screenToFlowPosition, getNode, fitView } = useReactFlow()

  // Data fetching
  const { data: canvasesData } = useCanvases(connectorId)
  const createCanvas = useCreateCanvas()
  const { data: qualysSchema } = useQualysSchema()

  // Determine or auto-create canvas
  const [canvasId, setCanvasId] = useState<string | null>(null)

  useEffect(() => {
    if (canvasesData && canvasesData.length > 0 && !canvasId) {
      setCanvasId(canvasesData[0].id)
    } else if (canvasesData && canvasesData.length === 0 && !canvasId && !createCanvas.isPending) {
      createCanvas.mutate(
        { connectorId, name: 'Default Canvas' },
        { onSuccess: (data) => setCanvasId(data.id) },
      )
    }
  }, [canvasesData, canvasId, connectorId, createCanvas])

  const { data: canvasEndpointsData } = useCanvasEndpoints(connectorId, canvasId ?? undefined)

  // Mutations
  const createCanvasEndpoint = useCreateCanvasEndpoint()
  const updateCanvasEndpoint = useUpdateCanvasEndpoint()
  const createEndpoint = useCreateEndpoint()
  const discoverFields = useEndpointDiscoverFields()
  const batchReplaceMappings = useBatchReplaceEndpointMappings()

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  // Context menu state
  const [contextMenuOpen, setContextMenuOpen] = useState(false)
  const [dropState, setDropState] = useState<{
    position: { x: number; y: number }
    sourceNodeId: string
    sourceHandleId: string
    screenPosition: { x: number; y: number }
  } | null>(null)

  // Save state
  const [isSaving, setIsSaving] = useState(false)

  // Delete confirmation dialog state
  const [deleteTarget, setDeleteTarget] = useState<{ nodeId: string; name: string } | null>(null)

  // Track initialization
  const [initialized, setInitialized] = useState(false)

  // Initialize canvas from backend data
  useEffect(() => {
    if (!canvasEndpointsData || !qualysSchema || initialized) return

    const endpointNodes: Node[] = canvasEndpointsData.map((ce, i) => ({
      id: ce.id,
      type: 'endpointNode',
      position: { x: 50 + i * 350, y: 50 },
      data: {
        endpointId: ce.endpoint_id,
        canvasEndpointId: ce.id,
        name: '', // Will be populated from endpoint data if available
        path: '',
        fields: [],
        parentRefId: ce.parent_ref_id,
        variableExtractions: ce.variable_extractions,
        maxConcurrency: ce.max_concurrency,
        isDiscovering: false,
        discoveryError: null,
      } satisfies EndpointNodeData,
    }))

    // Create chain edges from parent_ref_id relationships
    const chainEdges: Edge[] = canvasEndpointsData
      .filter((ce) => ce.parent_ref_id)
      .map((ce) => ({
        id: `chain-${ce.parent_ref_id}-${ce.id}`,
        source: ce.parent_ref_id!,
        sourceHandle: undefined,
        target: ce.id,
        targetHandle: `${ce.id}-target`,
        type: 'chain',
        data: { sourceField: '' } satisfies ChainEdgeData,
      }))

    // Create target panel node
    const targetNode: Node = {
      id: TARGET_PANEL_ID,
      type: 'targetPanel',
      position: { x: 800, y: 0 },
      data: {
        fields: qualysSchema.fields,
        linkedTargetFields: new Set(),
        linkedFieldOrder: new Map(),
      } satisfies TargetPanelData,
      draggable: false,
      selectable: false,
      style: { width: 280, height: 520 },
    }

    setNodes([...endpointNodes, targetNode])
    setEdges(chainEdges)
    setInitialized(true)

    // Auto-layout after a brief delay to let nodes render
    setTimeout(() => fitView({ padding: 0.2 }), 100)
  }, [canvasEndpointsData, qualysSchema, initialized, setNodes, setEdges, fitView])

  // Update target panel data when qualys schema or edges change
  useEffect(() => {
    if (!qualysSchema) return
    const mappingEdges = edges.filter((e) => e.type === 'mapping')
    const linkedFields = new Set(mappingEdges.map((e) => e.targetHandle).filter(Boolean) as string[])
    const linkedOrder = new Map<string, number>()
    mappingEdges.forEach((e, i) => {
      if (e.targetHandle) linkedOrder.set(e.targetHandle, i)
    })

    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === TARGET_PANEL_ID) {
          return {
            ...n,
            data: {
              fields: qualysSchema.fields,
              linkedTargetFields: linkedFields,
              linkedFieldOrder: linkedOrder,
            } satisfies TargetPanelData,
          }
        }
        return n
      }),
    )
  }, [qualysSchema, edges, setNodes])

  // Inject callbacks into endpoint node data
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.type !== 'endpointNode') return n
        const d = n.data as EndpointNodeData
        return {
          ...n,
          data: {
            ...d,
            onNameChange: (name: string) => {
              setNodes((prev) =>
                prev.map((nd) =>
                  nd.id === n.id ? { ...nd, data: { ...nd.data, name } } : nd,
                ),
              )
            },
            onPathChange: (path: string) => {
              setNodes((prev) =>
                prev.map((nd) =>
                  nd.id === n.id ? { ...nd, data: { ...nd.data, path } } : nd,
                ),
              )
            },
            onDiscoverFields: () => {
              const nodeData = n.data as EndpointNodeData
              if (!nodeData.endpointId) {
                toast({
                  title: 'Save first',
                  description: 'Save the canvas before discovering fields.',
                  variant: 'destructive',
                })
                return
              }
              setNodes((prev) =>
                prev.map((nd) =>
                  nd.id === n.id
                    ? { ...nd, data: { ...nd.data, isDiscovering: true, discoveryError: null } }
                    : nd,
                ),
              )
              discoverFields.mutate(
                { connectorId, endpointId: nodeData.endpointId },
                {
                  onSuccess: (data) => {
                    setNodes((prev) =>
                      prev.map((nd) =>
                        nd.id === n.id
                          ? {
                              ...nd,
                              data: {
                                ...nd.data,
                                fields: data.fields,
                                isDiscovering: false,
                                discoveryError: null,
                              },
                            }
                          : nd,
                      ),
                    )
                  },
                  onError: (err) => {
                    setNodes((prev) =>
                      prev.map((nd) =>
                        nd.id === n.id
                          ? {
                              ...nd,
                              data: {
                                ...nd.data,
                                isDiscovering: false,
                                discoveryError: err instanceof Error ? err.message : 'Discovery failed',
                              },
                            }
                          : nd,
                      ),
                    )
                  },
                },
              )
            },
            onDelete: () => {
              setDeleteTarget({ nodeId: n.id, name: (n.data as EndpointNodeData).name || 'Untitled' })
            },
            onMaxConcurrencyChange: (value: number) => {
              setNodes((prev) =>
                prev.map((nd) =>
                  nd.id === n.id ? { ...nd, data: { ...nd.data, maxConcurrency: value } } : nd,
                ),
              )
            },
          },
        }
      }),
    )
    // Only re-inject when nodes structurally change (add/remove), not on every data update
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, connectorId])

  // onConnect: handle-to-handle connection
  const onConnect = useCallback(
    (connection: Connection) => {
      const targetNode = getNode(connection.target ?? '')

      if (targetNode?.type === 'targetPanel') {
        // Mapping edge: field -> Qualys target
        const newEdge: Edge = {
          id: `mapping-${connection.sourceHandle}-${connection.targetHandle}-${Date.now()}`,
          source: connection.source ?? '',
          sourceHandle: connection.sourceHandle ?? undefined,
          target: connection.target ?? '',
          targetHandle: connection.targetHandle ?? undefined,
          type: 'mapping',
          data: { mappingType: 'direct' } satisfies MappingEdgeData,
        }
        setEdges((eds) => {
          // One-to-one: remove existing edges with same source or target handle
          const filtered = eds.filter(
            (e) =>
              e.type !== 'mapping' ||
              (e.sourceHandle !== connection.sourceHandle && e.targetHandle !== connection.targetHandle),
          )
          return [...filtered, newEdge]
        })
      } else if (targetNode?.type === 'endpointNode') {
        // Chain edge: parent field -> child endpoint
        const sourceField = connection.sourceHandle?.split('-').pop() ?? connection.sourceHandle ?? ''
        const newEdge: Edge = {
          id: `chain-${connection.source}-${connection.target}-${Date.now()}`,
          source: connection.source ?? '',
          sourceHandle: connection.sourceHandle ?? undefined,
          target: connection.target ?? '',
          targetHandle: connection.targetHandle ?? undefined,
          type: 'chain',
          data: { sourceField } satisfies ChainEdgeData,
        }
        setEdges((eds) => [...eds, newEdge])
      }
    },
    [getNode, setEdges],
  )

  // onConnectEnd: drag ended on empty canvas (D-05/D-06)
  const onConnectEnd: OnConnectEnd = useCallback(
    (event, connectionState) => {
      if (!connectionState.isValid) {
        const e = 'changedTouches' in event ? (event as TouchEvent).changedTouches[0] : (event as MouseEvent)
        const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
        setDropState({
          position,
          sourceNodeId: connectionState.fromNode?.id ?? '',
          sourceHandleId: connectionState.fromHandle?.id ?? '',
          screenPosition: { x: e.clientX, y: e.clientY },
        })
        setContextMenuOpen(true)
      }
    },
    [screenToFlowPosition],
  )

  // Create child endpoint from context menu (D-06)
  const handleCreateChildFromMenu = useCallback(() => {
    if (!dropState) return

    const sourceFieldName = dropState.sourceHandleId.split('.').pop() ?? dropState.sourceHandleId
    const newId = `temp-${Date.now()}`

    const newNode: Node = {
      id: newId,
      type: 'endpointNode',
      position: dropState.position,
      data: {
        endpointId: null,
        canvasEndpointId: null,
        name: '',
        path: `/{${sourceFieldName}}`,
        fields: [],
        parentRefId: dropState.sourceNodeId,
        variableExtractions: { [sourceFieldName]: dropState.sourceHandleId },
        maxConcurrency: 5,
        isDiscovering: false,
        discoveryError: null,
      } satisfies EndpointNodeData,
    }

    const newEdge: Edge = {
      id: `chain-${dropState.sourceNodeId}-${newId}-${Date.now()}`,
      source: dropState.sourceNodeId,
      sourceHandle: dropState.sourceHandleId,
      target: newId,
      targetHandle: `${newId}-target`,
      type: 'chain',
      data: { sourceField: dropState.sourceHandleId } satisfies ChainEdgeData,
    }

    setNodes((nds) => [...nds, newNode])
    setEdges((eds) => [...eds, newEdge])
    setContextMenuOpen(false)
    setDropState(null)
  }, [dropState, setNodes, setEdges])

  // Cycle detection for isValidConnection (D-12)
  const isValidConnection = useCallback(
    (connection: Connection) => {
      if (connection.source === connection.target) return false
      const targetNode = getNode(connection.target ?? '')
      if (targetNode?.type === 'endpointNode') {
        return !wouldCreateCycle(connection.source ?? '', connection.target ?? '', edges)
      }
      return true // mapping connections to target panel always valid
    },
    [edges, getNode],
  )

  // Create new endpoint (toolbar D-02)
  const handleCreateEndpoint = useCallback(() => {
    const newId = `temp-${Date.now()}`
    const newNode: Node = {
      id: newId,
      type: 'endpointNode',
      position: { x: 200, y: 200 },
      data: {
        endpointId: null,
        canvasEndpointId: null,
        name: '',
        path: '',
        fields: [],
        parentRefId: null,
        variableExtractions: null,
        maxConcurrency: 5,
        isDiscovering: false,
        discoveryError: null,
      } satisfies EndpointNodeData,
    }
    setNodes((nds) => [...nds, newNode])
  }, [setNodes])

  // Auto Layout (toolbar D-11)
  const handleAutoLayout = useCallback(() => {
    const endpointNodes = nodes.filter((n) => n.type === 'endpointNode')
    if (endpointNodes.length === 0) return

    const positions = getLayoutedPositions(endpointNodes, edges, 'LR')

    setNodes((nds) =>
      nds.map((n) => {
        if (n.type === 'endpointNode') {
          const pos = positions.get(n.id)
          if (pos) return { ...n, position: pos }
        }
        // Position target panel to the right of all endpoint nodes
        if (n.id === TARGET_PANEL_ID) {
          let maxX = 0
          positions.forEach((p) => {
            if (p.x + 300 > maxX) maxX = p.x + 300
          })
          return { ...n, position: { x: maxX + 100, y: 0 } }
        }
        return n
      }),
    )

    setTimeout(() => fitView({ padding: 0.2 }), 50)
  }, [nodes, edges, setNodes, fitView])

  // canSave computed (D-13)
  const canSave = useMemo(() => {
    const endpointNodes = nodes.filter((n) => n.type === 'endpointNode')
    const hasFields = endpointNodes.some((n) => {
      const d = n.data as EndpointNodeData
      return d.fields.length > 0
    })
    if (!hasFields) return false

    // Check for at least one mapping edge to an identity field
    const mappingEdges = edges.filter((e) => e.type === 'mapping')
    if (mappingEdges.length === 0) return false

    const identityFields = new Set(
      (qualysSchema?.fields ?? []).filter((f) => f.is_identity).map((f) => f.field),
    )
    return mappingEdges.some((e) => e.targetHandle && identityFields.has(e.targetHandle))
  }, [nodes, edges, qualysSchema])

  // Save Canvas (toolbar IC-06)
  const handleSave = useCallback(async () => {
    if (!canvasId) return
    setIsSaving(true)

    try {
      const endpointNodes = nodes.filter((n) => n.type === 'endpointNode')

      // Step a: Create base endpoints for unsaved nodes
      for (const node of endpointNodes) {
        const d = node.data as EndpointNodeData
        if (d.endpointId === null) {
          const created = await createEndpoint.mutateAsync({
            connectorId,
            endpoint: { name: d.name || 'Untitled', path: d.path },
          })
          setNodes((prev) =>
            prev.map((n) =>
              n.id === node.id
                ? { ...n, data: { ...n.data, endpointId: String(created.id) } }
                : n,
            ),
          )
          // Update local reference for subsequent steps
          ;(node.data as EndpointNodeData).endpointId = String(created.id)
        }
      }

      // Step b: Create canvas-endpoints for unsaved nodes
      for (const node of endpointNodes) {
        const d = node.data as EndpointNodeData
        if (d.canvasEndpointId === null && d.endpointId) {
          // Find parent_ref_id from chain edges
          const parentEdge = edges.find((e) => e.type === 'chain' && e.target === node.id)
          const parentRefId = parentEdge?.source ?? null
          // Resolve parent ref to canvas endpoint ID
          let resolvedParentRefId: string | null = null
          if (parentRefId) {
            const parentNode = nodes.find((n) => n.id === parentRefId)
            if (parentNode) {
              resolvedParentRefId = (parentNode.data as EndpointNodeData).canvasEndpointId
            }
          }

          const created = await createCanvasEndpoint.mutateAsync({
            connectorId,
            canvasId,
            payload: {
              endpoint_id: d.endpointId,
              parent_ref_id: resolvedParentRefId,
              variable_extractions: d.variableExtractions,
              max_concurrency: d.maxConcurrency,
            },
          })
          setNodes((prev) =>
            prev.map((n) =>
              n.id === node.id
                ? { ...n, data: { ...n.data, canvasEndpointId: created.id } }
                : n,
            ),
          )
          ;(node.data as EndpointNodeData).canvasEndpointId = created.id
        }
      }

      // Step c: Update existing canvas-endpoints
      for (const node of endpointNodes) {
        const d = node.data as EndpointNodeData
        if (d.canvasEndpointId && d.endpointId) {
          const parentEdge = edges.find((e) => e.type === 'chain' && e.target === node.id)
          const parentRefId = parentEdge?.source ?? null
          let resolvedParentRefId: string | null = null
          if (parentRefId) {
            const parentNode = nodes.find((n) => n.id === parentRefId)
            if (parentNode) {
              resolvedParentRefId = (parentNode.data as EndpointNodeData).canvasEndpointId
            }
          }

          await updateCanvasEndpoint.mutateAsync({
            connectorId,
            canvasId,
            canvasEndpointId: d.canvasEndpointId,
            payload: {
              parent_ref_id: resolvedParentRefId,
              variable_extractions: d.variableExtractions,
              max_concurrency: d.maxConcurrency,
            },
          })
        }
      }

      // Step d: Batch-replace field mappings per endpoint
      const mappingEdges = edges.filter((e) => e.type === 'mapping')
      // Group mapping edges by source node (endpoint)
      const mappingsByEndpoint = new Map<string, Edge[]>()
      for (const edge of mappingEdges) {
        const existing = mappingsByEndpoint.get(edge.source) ?? []
        existing.push(edge)
        mappingsByEndpoint.set(edge.source, existing)
      }

      for (const [nodeId, nodeEdges] of mappingsByEndpoint) {
        const node = nodes.find((n) => n.id === nodeId)
        if (!node) continue
        const d = node.data as EndpointNodeData
        if (!d.endpointId) continue

        const mappings = nodeEdges.map((e) => ({
          source_field: e.sourceHandle ?? '',
          target_field: e.targetHandle ?? '',
          mapping_type: 'direct_copy' as const,
        }))

        await batchReplaceMappings.mutateAsync({
          connectorId,
          endpointId: d.endpointId,
          mappings,
        })
      }

      toast({ title: 'Canvas saved', description: 'All endpoints and mappings have been saved.' })
    } catch {
      toast({
        title: 'Save failed',
        description: 'Failed to save canvas. Please try again.',
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }, [
    canvasId,
    nodes,
    edges,
    connectorId,
    createEndpoint,
    createCanvasEndpoint,
    updateCanvasEndpoint,
    batchReplaceMappings,
    setNodes,
    toast,
  ])

  // Delete endpoint (IC-07)
  const handleDeleteEndpoint = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId))
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setDeleteTarget(null)
    },
    [setNodes, setEdges],
  )

  // Endpoint nodes for empty state check
  const endpointNodes = nodes.filter((n) => n.type === 'endpointNode')

  return (
    <div className="flex flex-col h-full">
      <CanvasToolbar
        connectorId={connectorId}
        connectorName={connectorName}
        onCreateEndpoint={handleCreateEndpoint}
        onAutoLayout={handleAutoLayout}
        onSave={handleSave}
        isSaving={isSaving}
        canSave={canSave}
      />
      <div className="flex-1 relative">
        {endpointNodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
            <div className="text-center text-muted-foreground p-8">
              <p className="text-lg font-medium">No endpoints on this canvas</p>
              <p className="text-sm mt-2">
                Create an endpoint to start building your API chain. Drag from a field handle to
                create child endpoints.
              </p>
            </div>
          </div>
        )}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onConnectEnd={onConnectEnd}
          isValidConnection={isValidConnection}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          connectionLineComponent={DashedConnectionLine}
          fitView
          panOnDrag
          zoomOnScroll
          nodesDraggable
        >
          <Background variant={BackgroundVariant.Dots} gap={16} />
        </ReactFlow>
        <CanvasContextMenu
          open={contextMenuOpen}
          onOpenChange={setContextMenuOpen}
          position={dropState?.screenPosition ?? { x: 0, y: 0 }}
          onCreateChild={handleCreateChildFromMenu}
        />
      </div>

      {/* Delete confirmation dialog (IC-07) */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete endpoint</DialogTitle>
            <DialogDescription>
              Delete endpoint &apos;{deleteTarget?.name}&apos;? This removes it from the canvas and
              any chain connections. The base endpoint definition is preserved.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && handleDeleteEndpoint(deleteTarget.nodeId)}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export function ChainCanvas(props: ChainCanvasProps) {
  return (
    <ReactFlowProvider>
      <ChainCanvasInner {...props} />
    </ReactFlowProvider>
  )
}
