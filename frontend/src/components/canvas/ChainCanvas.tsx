import '@xyflow/react/dist/style.css'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
  type EdgeChange,
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
import { useEndpoints, useCreateEndpoint } from '@/hooks/queries/useEndpoints'
import { useEndpointDiscoverFields, useCanvasDiscoverFields } from '@/hooks/queries/useEndpointDiscover'
import { useBatchReplaceEndpointMappings } from '@/hooks/queries/useEndpointMappings'
import { useDryRun } from '@/hooks/queries/useDryRun'
import { apiClient } from '@/lib/api-client'
import { ROUTES } from '@/routes/constants'
import type { FieldMapping } from '@/types/api'
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
  DiscoverResponse,
  TargetPanelData,
  ExclusionRule,
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

/** BFS to collect all descendant node IDs from chain edges */
function getDescendantNodeIds(startNodeId: string, edges: Edge[]): string[] {
  const descendants: string[] = []
  const queue = [startNodeId]
  while (queue.length > 0) {
    const current = queue.shift()!
    const children = edges
      .filter((e) => e.type === 'chain' && e.source === current)
      .map((e) => e.target)
    descendants.push(...children)
    queue.push(...children)
  }
  return descendants
}

interface ChainCanvasProps {
  connectorId: string
  connectorName: string
  initialCanvasId?: string
}

const TARGET_PANEL_ID = 'target-panel'

function ChainCanvasInner({ connectorId, connectorName, initialCanvasId }: ChainCanvasProps) {
  const { toast } = useToast()
  const navigate = useNavigate()
  const { screenToFlowPosition, getNode, fitView } = useReactFlow()

  // Data fetching
  const { data: canvasesData } = useCanvases(connectorId)
  const createCanvas = useCreateCanvas()
  const { data: qualysSchema } = useQualysSchema()

  // Determine or auto-create canvas — prefer URL-provided canvasId
  const [canvasId, setCanvasId] = useState<string | null>(initialCanvasId ?? null)

  useEffect(() => {
    if (initialCanvasId) {
      setCanvasId(initialCanvasId)
      return
    }
    if (canvasesData && canvasesData.length > 0 && !canvasId) {
      setCanvasId(canvasesData[0].id)
    } else if (canvasesData && canvasesData.length === 0 && !canvasId && !createCanvas.isPending) {
      createCanvas.mutate(
        { connectorId, name: 'Default Canvas' },
        { onSuccess: (data) => setCanvasId(data.id) },
      )
    }
  }, [canvasesData, canvasId, connectorId, createCanvas, initialCanvasId])

  const { data: canvasEndpointsData } = useCanvasEndpoints(connectorId, canvasId ?? undefined)
  const { data: endpointsData } = useEndpoints(connectorId)

  // Mutations
  const createCanvasEndpoint = useCreateCanvasEndpoint()
  const updateCanvasEndpoint = useUpdateCanvasEndpoint()
  const createEndpoint = useCreateEndpoint()
  const discoverFields = useEndpointDiscoverFields()
  const canvasDiscoverFields = useCanvasDiscoverFields()
  const batchReplaceMappings = useBatchReplaceEndpointMappings()
  const dryRun = useDryRun()

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  // Keep a ref to latest nodes so callbacks always see current endpointId
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes

  // Keep a ref to latest edges for cascade deletion lookups in callbacks
  const edgesRef = useRef(edges)
  edgesRef.current = edges

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

  // Delete confirmation dialog state (with cascade info)
  const [deleteTarget, setDeleteTarget] = useState<{
    nodeId: string
    name: string
    descendantIds: string[]
    descendantNames: string[]
  } | null>(null)

  // Track initialization
  const [initialized, setInitialized] = useState(false)

  // Initialize canvas from backend data
  useEffect(() => {
    if (!canvasEndpointsData || !endpointsData || !qualysSchema || initialized) return

    // Build lookup from endpoint_id to endpoint details
    const endpointLookup = new Map(
      endpointsData.map((ep) => [String(ep.id), ep]),
    )

    const endpointNodes: Node[] = canvasEndpointsData.map((ce, i) => {
      const ep = endpointLookup.get(ce.endpoint_id)
      return {
        id: ce.id,
        type: 'endpointNode',
        position: { x: 50 + i * 350, y: 50 },
        data: {
          endpointId: ce.endpoint_id,
          canvasEndpointId: ce.id,
          name: ep?.name ?? '',
          path: ep?.path ?? '',
          fields: [],
          parentRefId: ce.parent_ref_id,
          variableExtractions: ce.variable_extractions,
          maxConcurrency: ce.max_concurrency,
          isDiscovering: false,
          discoveryError: null,
          exclusionRules: ce.exclusion_rules ?? [],
        } satisfies EndpointNodeData,
      }
    })

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

    // After init, auto-discover fields for root endpoints and restore mapping edges
    const restoreFieldsAndMappings = async () => {
      const updatedNodes = [...endpointNodes]
      const mappingEdges: Edge[] = []

      for (const node of updatedNodes) {
        const d = node.data as EndpointNodeData
        if (!d.endpointId) continue

        // Discover fields for endpoints without template variables
        const hasTemplateVars = /\{[^}]+\}/.test(d.path)
        if (!hasTemplateVars) {
          try {
            const { data: discovered } = await apiClient.get<DiscoverResponse>(
              `/connectors/${connectorId}/endpoints/${d.endpointId}/fields/discover`,
            )
            ;(node.data as EndpointNodeData).fields = discovered.fields
            // D-04: Toast for auto-detected data root during initial load
            if (discovered.auto_detected_data_root) {
              toast({ title: `Auto-detected data root: ${discovered.auto_detected_data_root}` })
            }
          } catch {
            // Non-critical — fields will be empty
          }
        }

        // Load saved mappings and reconstruct mapping edges
        try {
          const { data: mappings } = await apiClient.get<FieldMapping[]>(
            `/connectors/${connectorId}/endpoints/${d.endpointId}/mappings`,
          )
          for (const mapping of mappings) {
            mappingEdges.push({
              id: `mapping-${node.id}-${mapping.source_field}-${mapping.target_field}`,
              source: node.id,
              sourceHandle: mapping.source_field,
              target: TARGET_PANEL_ID,
              targetHandle: mapping.target_field,
              type: 'mapping',
              data: {
                sourceField: mapping.source_field,
                targetField: mapping.target_field,
                mappingType: mapping.mapping_type === 'direct_copy' ? 'direct' : mapping.mapping_type === 'static_default' ? 'static' : 'conditional',
              } satisfies MappingEdgeData,
            })
          }
        } catch {
          // Non-critical — mappings will be empty
        }
      }

      setNodes((prev) =>
        prev.map((n) => {
          const updated = updatedNodes.find((u) => u.id === n.id)
          return updated ? { ...n, data: { ...n.data, ...(updated.data as EndpointNodeData) } } : n
        }),
      )
      if (mappingEdges.length > 0) {
        setEdges((prev) => [...prev, ...mappingEdges])
      }

      setTimeout(() => fitView({ padding: 0.2 }), 100)
    }

    restoreFieldsAndMappings()

    // Auto-layout after a brief delay to let nodes render
    setTimeout(() => fitView({ padding: 0.2 }), 100)
  }, [canvasEndpointsData, endpointsData, qualysSchema, initialized, setNodes, setEdges, fitView, connectorId])

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
              // Read current node data from ref to avoid stale closure after save
              const currentNode = nodesRef.current.find((nd) => nd.id === n.id)
              const currentEndpointId = currentNode
                ? (currentNode.data as EndpointNodeData).endpointId
                : null
              if (!currentEndpointId) {
                toast({
                  title: 'Save first',
                  description: 'Save the canvas before discovering fields.',
                  variant: 'destructive',
                })
                return
              }
              // Determine if this is a child endpoint needing canvas-aware discovery (D-01)
              const currentPath = currentNode
                ? (currentNode.data as EndpointNodeData).path
                : ''
              const hasTemplateVars = /\{[^}]+\}/.test(currentPath)

              if (hasTemplateVars) {
                // Canvas-aware discovery for child endpoints (D-01, D-08)
                const currentCanvasEndpointId = currentNode
                  ? (currentNode.data as EndpointNodeData).canvasEndpointId
                  : null
                if (!currentCanvasEndpointId || !canvasId) {
                  // Same "Save first" pattern (D-02)
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
                canvasDiscoverFields.mutate(
                  {
                    connectorId,
                    canvasId,
                    canvasEndpointRefId: currentCanvasEndpointId,
                  },
                  {
                    onSuccess: (data) => {
                      // Filter out _parent.* fields -- each node shows only its own fields (D-03)
                      const ownFields = data.fields.filter(
                        (f) => !f.path.startsWith('_parent.')
                      )
                      setNodes((prev) =>
                        prev.map((nd) =>
                          nd.id === n.id
                            ? {
                                ...nd,
                                data: {
                                  ...nd.data,
                                  fields: ownFields,
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
                                  discoveryError:
                                    err instanceof Error ? err.message : 'Discovery failed',
                                },
                              }
                            : nd,
                        ),
                      )
                    },
                  },
                )
              } else {
                // Root endpoint -- existing flat discovery (unchanged behavior)
                setNodes((prev) =>
                  prev.map((nd) =>
                    nd.id === n.id
                      ? { ...nd, data: { ...nd.data, isDiscovering: true, discoveryError: null } }
                      : nd,
                  ),
                )
                discoverFields.mutate(
                  { connectorId, endpointId: currentEndpointId },
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
                      // D-04: Toast notification when auto-detect finds a data root
                      if (data.auto_detected_data_root) {
                        toast({ title: `Auto-detected data root: ${data.auto_detected_data_root}` })
                      }
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
                                  discoveryError:
                                    err instanceof Error ? err.message : 'Discovery failed',
                                },
                              }
                            : nd,
                        ),
                      )
                    },
                  },
                )
              }
            },
            onDelete: () => {
              const descendantIds = getDescendantNodeIds(n.id, edgesRef.current)
              const descendantNames = descendantIds.map((did) => {
                const dNode = nodesRef.current.find((nd) => nd.id === did)
                return dNode ? (dNode.data as EndpointNodeData).name || 'Untitled' : 'Unknown'
              })
              setDeleteTarget({
                nodeId: n.id,
                name: (n.data as EndpointNodeData).name || 'Untitled',
                descendantIds,
                descendantNames,
              })
            },
            onMaxConcurrencyChange: (value: number) => {
              setNodes((prev) =>
                prev.map((nd) =>
                  nd.id === n.id ? { ...nd, data: { ...nd.data, maxConcurrency: value } } : nd,
                ),
              )
            },
            onExclusionRulesChange: (rules: ExclusionRule[]) => {
              setNodes((prev) =>
                prev.map((nd) =>
                  nd.id === n.id ? { ...nd, data: { ...nd.data, exclusionRules: rules } } : nd,
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
        exclusionRules: [],
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
    (connection: Edge | Connection) => {
      if (connection.source === connection.target) return false
      const target = connection.target ?? ''
      const targetNode = getNode(target)
      if (targetNode?.type === 'endpointNode') {
        return !wouldCreateCycle(connection.source ?? '', target, edges)
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
        exclusionRules: [],
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
    if (endpointNodes.length === 0) return false

    // Allow save when there are any endpoint nodes with content
    const hasContent = endpointNodes.some((n) => {
      const d = n.data as EndpointNodeData
      return d.name || d.path
    })
    return hasContent
  }, [nodes])

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
              exclusion_rules: d.exclusionRules.length > 0 ? d.exclusionRules : null,
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
              exclusion_rules: d.exclusionRules.length > 0 ? d.exclusionRules : null,
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

  // Delete endpoint with cascade (IC-07, D-05, D-06)
  const handleDeleteEndpoint = useCallback(
    (nodeId: string) => {
      const descendantIds = deleteTarget?.descendantIds ?? getDescendantNodeIds(nodeId, edges)
      const allIdsToRemove = new Set([nodeId, ...descendantIds])
      setNodes((nds) => nds.filter((n) => !allIdsToRemove.has(n.id)))
      setEdges((eds) => eds.filter((e) => !allIdsToRemove.has(e.source) && !allIdsToRemove.has(e.target)))
      setDeleteTarget(null)
    },
    [setNodes, setEdges, edges, deleteTarget],
  )

  // Intercept edge changes to prevent silent chain edge removal (D-05, D-06)
  const handleEdgesChange = useCallback(
    (changes: EdgeChange<Edge>[]) => {
      // Intercept removal of chain edges -- must cascade
      const chainRemovals = changes.filter(
        (c) => c.type === 'remove' && edges.find((e) => e.id === c.id && e.type === 'chain'),
      )
      if (chainRemovals.length > 0) {
        // Find the child node (target of the chain edge) and trigger cascade confirmation
        const removedEdge = edges.find(
          (e) => e.id === (chainRemovals[0] as { type: 'remove'; id: string }).id,
        )
        if (removedEdge) {
          const childNode = nodes.find((n) => n.id === removedEdge.target)
          const childName = childNode
            ? (childNode.data as EndpointNodeData).name || 'Untitled'
            : 'Unknown'
          const allDescendantIds = [
            removedEdge.target,
            ...getDescendantNodeIds(removedEdge.target, edges),
          ]
          const allDescendantNames = allDescendantIds.map((did) => {
            const dNode = nodes.find((nd) => nd.id === did)
            return dNode ? (dNode.data as EndpointNodeData).name || 'Untitled' : 'Unknown'
          })
          setDeleteTarget({
            nodeId: removedEdge.target,
            name: childName,
            descendantIds: allDescendantIds.slice(1),
            descendantNames: allDescendantNames.slice(1),
          })
        }
        // Filter out chain edge removals -- they'll be applied after confirmation
        const nonChainChanges = changes.filter(
          (c) =>
            !(c.type === 'remove' && edges.find((e) => e.id === c.id && e.type === 'chain')),
        )
        if (nonChainChanges.length > 0) {
          onEdgesChange(nonChainChanges)
        }
        return
      }
      // Non-chain edge changes pass through normally
      onEdgesChange(changes)
    },
    [edges, nodes, onEdgesChange],
  )

  // Endpoint nodes for empty state check
  const endpointNodes = nodes.filter((n) => n.type === 'endpointNode')

  // Dry-run support (D-06): detect chains and wire dry-run button
  const hasChain = endpointNodes.some((n) => (n.data as EndpointNodeData).parentRefId != null)

  const handleDryRun = useCallback(async () => {
    if (!canvasId) return
    try {
      const result = await dryRun.mutateAsync({ connectorId, canvasId })
      navigate(ROUTES.dryRunResults(connectorId, canvasId), {
        state: { dryRunResults: result },
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      toast({
        title: 'Dry run failed',
        description: `${message}. Check connector credentials and endpoint configuration.`,
        variant: 'destructive',
      })
    }
  }, [canvasId, connectorId, dryRun, navigate, toast])

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
        hasChain={hasChain}
        onDryRun={handleDryRun}
        isDryRunning={dryRun.isPending}
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
          onEdgesChange={handleEdgesChange}
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

      {/* Delete confirmation dialog with cascade support (IC-07, D-05, D-06) */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {deleteTarget && deleteTarget.descendantIds.length > 0
                ? 'Delete endpoint and descendants?'
                : 'Delete endpoint'}
            </DialogTitle>
            <DialogDescription>
              {deleteTarget && deleteTarget.descendantIds.length > 0
                ? `This will remove ${deleteTarget.name} and ${deleteTarget.descendantIds.length} descendant endpoint(s) from this canvas. Discovered fields and mappings for these endpoints will be lost.`
                : `Delete endpoint '${deleteTarget?.name}'? This removes it from the canvas and any chain connections. The base endpoint definition is preserved.`}
            </DialogDescription>
          </DialogHeader>
          {deleteTarget && deleteTarget.descendantNames.length > 0 && (
            <div className="text-sm text-muted-foreground px-1">
              <p className="font-medium mb-1">Affected endpoints:</p>
              <ul className="list-disc pl-4 space-y-0.5">
                {deleteTarget.descendantNames.map((name, i) => (
                  <li key={i}>{name}</li>
                ))}
              </ul>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              {deleteTarget && deleteTarget.descendantIds.length > 0 ? 'Keep endpoints' : 'Cancel'}
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && handleDeleteEndpoint(deleteTarget.nodeId)}
            >
              {deleteTarget && deleteTarget.descendantIds.length > 0 ? 'Delete all' : 'Delete'}
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
