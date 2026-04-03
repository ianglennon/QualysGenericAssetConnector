/**
 * Phase 61 integration tests for ChainCanvas wiring gaps:
 *
 * Gap 1 (DET-03): ChainCanvas calls useBaseDetection(nodes, edges) and uses its output
 *   to drive the optimistic isBase update effect.
 *
 * Gap 2 (DET-03): treeOrder is populated from ce.tree_order during node construction.
 *
 * Gap 3 (UX-01): CanvasWarningBanner is rendered with visible={!hasIdentityFields}.
 */

import { describe, it, vi, expect, beforeAll } from 'vitest'
import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Environment setup
// ---------------------------------------------------------------------------

beforeAll(() => {
  class MockResizeObserver {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  global.ResizeObserver = MockResizeObserver as any
})

// ---------------------------------------------------------------------------
// Mock react-router-dom (including useNavigate which ChainCanvas requires)
// ---------------------------------------------------------------------------

vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
  useNavigate: () => vi.fn(),
}))

// ---------------------------------------------------------------------------
// Mutable state for test control of useBaseDetection output
// ---------------------------------------------------------------------------

let mockBaseDetectionResult = { baseNodeId: null as string | null, hasIdentityFields: false }

vi.mock('@/hooks/useBaseDetection', () => ({
  useBaseDetection: vi.fn((_nodes: unknown, _edges: unknown) => mockBaseDetectionResult),
}))

// ---------------------------------------------------------------------------
// Mutable state for CanvasWarningBanner prop capture
// ---------------------------------------------------------------------------

let capturedBannerVisible: boolean | undefined = undefined

vi.mock('@/components/canvas/CanvasWarningBanner', () => ({
  CanvasWarningBanner: vi.fn(({ visible }: { visible: boolean }) => {
    capturedBannerVisible = visible
    return visible ? (
      <div data-testid="canvas-warning-banner" />
    ) : null
  }),
}))

// ---------------------------------------------------------------------------
// Captured ReactFlow props for test access
// ---------------------------------------------------------------------------

let capturedRFNodes: any[] = []
let capturedRFEdges: any[] = []

// eslint-disable-next-line @typescript-eslint/no-explicit-any
vi.mock('@xyflow/react', async () => {
  const { useState } = await import('react')

  const useNodesStateMock = vi.fn((init: any[] = []) => {
    const [nodes, setNodes] = useState(init)
    return [nodes, setNodes, vi.fn()]
  })

  const useEdgesStateMock = vi.fn((init: any[] = []) => {
    const [edges, setEdges] = useState(init)
    return [edges, setEdges, vi.fn()]
  })

  return {
    ReactFlow: (props: any) => {
      capturedRFNodes = props.nodes ?? []
      capturedRFEdges = props.edges ?? []
      return (
        <div data-testid="react-flow">
          {(props.nodes ?? []).map((node: any) => (
            <div
              key={node.id}
              data-testid="rf-node"
              data-node-id={node.id}
              data-node-type={node.type}
              data-node-is-base={String(node.data?.isBase ?? false)}
              data-node-tree-order={String(node.data?.treeOrder ?? '')}
            />
          ))}
          {props.children}
        </div>
      )
    },
    ReactFlowProvider: ({ children }: any) => <>{children}</>,
    useNodesState: useNodesStateMock,
    useEdgesState: useEdgesStateMock,
    useReactFlow: () => ({
      screenToFlowPosition: (pos: { x: number; y: number }) => pos,
      getNode: (id: string) => {
        if (id === 'target-panel') return { id: 'target-panel', type: 'targetPanel' }
        return undefined
      },
      fitView: vi.fn(),
    }),
    useUpdateNodeInternals: () => vi.fn(),
    useNodeId: () => 'test-node-id',
    Handle: ({ id, type }: { id?: string; type?: string }) => (
      <div data-testid="handle" data-id={id} data-type={type} />
    ),
    Position: { Left: 'left', Right: 'right' },
    BaseEdge: () => <path />,
    EdgeLabelRenderer: ({ children }: any) => <>{children}</>,
    getSmoothStepPath: () => ['M0,0', 50, 50],
    Background: () => null,
    BackgroundVariant: { Dots: 'dots' },
    addEdge: vi.fn((edge: any, edges: any[]) => [...edges, edge]),
  }
})

// ---------------------------------------------------------------------------
// Query hook mocks (shared base)
// ---------------------------------------------------------------------------

vi.mock('@/hooks/queries/useCanvases', () => {
  const canvases = {
    data: [
      {
        id: 'canvas-1',
        connector_id: 'conn-1',
        name: 'Default Canvas',
        base_canvas_endpoint_id: null,
      },
    ],
    isLoading: false,
  }
  const createCanvas = {
    mutate: vi.fn(),
    isPending: false,
    mutateAsync: vi.fn().mockResolvedValue({ id: 'canvas-new' }),
  }
  return {
    useCanvases: vi.fn(() => canvases),
    useCreateCanvas: vi.fn(() => createCanvas),
  }
})

// useCanvasEndpoints is configured per-test via the mutable endpoints array
const mockCanvasEndpointsData: any[] = []

vi.mock('@/hooks/queries/useCanvasEndpoints', () => {
  const createCE = { mutateAsync: vi.fn().mockResolvedValue({ id: 'ce-new' }), isPending: false }
  const updateCE = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
  const deleteCE = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
  return {
    useCanvasEndpoints: vi.fn(() => ({ data: mockCanvasEndpointsData, isLoading: false })),
    useCreateCanvasEndpoint: vi.fn(() => createCE),
    useUpdateCanvasEndpoint: vi.fn(() => updateCE),
    useDeleteCanvasEndpoint: vi.fn(() => deleteCE),
  }
})

vi.mock('@/hooks/queries/useEndpoints', () => {
  // Matching endpoint records so ChainCanvas can look up name/path from ep.id
  const endpoints = {
    data: [
      { id: 'ep-1', name: 'Endpoint Alpha', path: '/api/alpha' },
      { id: 'ep-2', name: 'Endpoint Beta', path: '/api/beta' },
    ],
    isLoading: false,
  }
  const createEP = {
    mutateAsync: vi.fn().mockResolvedValue({ id: 'ep-new', name: 'New', path: '/new' }),
    isPending: false,
  }
  return {
    useEndpoints: vi.fn(() => endpoints),
    useCreateEndpoint: vi.fn(() => createEP),
  }
})

vi.mock('@/hooks/queries/useEndpointDiscover', () => {
  const discover = { mutate: vi.fn(), isPending: false }
  return {
    useEndpointDiscoverFields: vi.fn(() => discover),
    useCanvasDiscoverFields: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  }
})

vi.mock('@/hooks/queries/useEndpointMappings', () => {
  const batch = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
  return { useBatchReplaceEndpointMappings: vi.fn(() => batch) }
})

vi.mock('@/hooks/queries/useQualysSchema', () => {
  const schema = {
    data: {
      fields: [
        { field: 'hostName', is_identity: true },
        { field: 'name', is_identity: false },
      ],
    },
    isLoading: false,
  }
  return { useQualysSchema: vi.fn(() => schema) }
})

vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: vi.fn() })),
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { fields: [] } }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/hooks/queries/useDryRun', () => ({
  useDryRun: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

// ---------------------------------------------------------------------------
// Import component under test AFTER all vi.mock declarations
// ---------------------------------------------------------------------------

import { ChainCanvas } from './ChainCanvas'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

const defaultProps = {
  connectorId: 'conn-1',
  connectorName: 'Test Connector',
}

// ---------------------------------------------------------------------------
// Gap 1 (DET-03): ChainCanvas calls useBaseDetection(nodes, edges)
// ---------------------------------------------------------------------------

describe('DET-03: ChainCanvas integrates useBaseDetection hook', () => {
  it('calls useBaseDetection with the current nodes and edges on render', async () => {
    const { useBaseDetection } = await import('@/hooks/useBaseDetection')
    const spy = vi.mocked(useBaseDetection)
    spy.mockClear()

    render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(screen.getByTestId('react-flow')).toBeInTheDocument()
    })

    // useBaseDetection must have been called at least once with arrays (nodes, edges)
    expect(spy).toHaveBeenCalled()
    const [nodesArg, edgesArg] = spy.mock.calls[0]
    expect(Array.isArray(nodesArg)).toBe(true)
    expect(Array.isArray(edgesArg)).toBe(true)
  })

  it('optimistic effect wires baseNodeId from useBaseDetection to update node isBase state', async () => {
    // Set up one canvas endpoint so an endpoint node is built
    mockCanvasEndpointsData.length = 0
    mockCanvasEndpointsData.push({
      id: 'ce-alpha',
      canvas_id: 'canvas-1',
      endpoint_id: 'ep-1',
      parent_ref_id: null,
      field_role: 'primary',
      variable_extractions: null,
      max_concurrency: 1,
      tree_order: 0,
      exclusion_rules: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })

    const { useBaseDetection } = await import('@/hooks/useBaseDetection')
    // Start with no base: all nodes should have isBase=false
    vi.mocked(useBaseDetection).mockReturnValue({ baseNodeId: null, hasIdentityFields: false })

    const { rerender } = render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

    await waitFor(() => {
      // The endpoint node must appear in the ReactFlow mock (initialization ran)
      const nodes = screen.queryAllByTestId('rf-node')
      const epNode = nodes.find((n) => n.getAttribute('data-node-id') === 'ce-alpha')
      expect(epNode).not.toBeUndefined()
    })

    // Verify useBaseDetection was called (hook wired into component)
    expect(vi.mocked(useBaseDetection)).toHaveBeenCalled()

    // Now update the mock to return baseNodeId='ce-alpha' and trigger re-render
    vi.mocked(useBaseDetection).mockReturnValue({ baseNodeId: 'ce-alpha', hasIdentityFields: true })

    await act(async () => {
      rerender(<ChainCanvas {...defaultProps} />)
    })

    await waitFor(() => {
      const nodes = screen.getAllByTestId('rf-node')
      const epNode = nodes.find((n) => n.getAttribute('data-node-id') === 'ce-alpha')
      // After the optimistic effect runs with new baseNodeId, the node should have isBase=true
      expect(epNode?.getAttribute('data-node-is-base')).toBe('true')
    }, { timeout: 3000 })

    // Cleanup
    mockCanvasEndpointsData.length = 0
    mockBaseDetectionResult = { baseNodeId: null, hasIdentityFields: false }
    vi.mocked(useBaseDetection).mockReturnValue({ baseNodeId: null, hasIdentityFields: false })
  })
})

// ---------------------------------------------------------------------------
// Gap 2 (DET-03): treeOrder is populated from ce.tree_order during node construction
// ---------------------------------------------------------------------------

describe('DET-03: ChainCanvas populates treeOrder on endpoint nodes from API data', () => {
  it('endpoint nodes receive treeOrder matching ce.tree_order from the canvas endpoint response', async () => {
    mockCanvasEndpointsData.length = 0
    mockCanvasEndpointsData.push(
      {
        id: 'ce-a',
        canvas_id: 'canvas-1',
        endpoint_id: 'ep-1',
        parent_ref_id: null,
        field_role: 'primary',
        variable_extractions: null,
        max_concurrency: 1,
        tree_order: 7,
        exclusion_rules: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'ce-b',
        canvas_id: 'canvas-1',
        endpoint_id: 'ep-2',
        parent_ref_id: 'ce-a',
        field_role: 'child',
        variable_extractions: null,
        max_concurrency: 1,
        tree_order: 3,
        exclusion_rules: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    )

    mockBaseDetectionResult = { baseNodeId: null, hasIdentityFields: false }

    render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

    await waitFor(() => {
      const nodes = screen.getAllByTestId('rf-node')
      // Expect two endpoint nodes built from the two canvas endpoint records
      const endpointNodes = nodes.filter(
        (n) => n.getAttribute('data-node-type') === 'endpointNode',
      )
      expect(endpointNodes.length).toBe(2)
    })

    await waitFor(() => {
      const nodes = screen.getAllByTestId('rf-node')
      const endpointNodes = nodes.filter(
        (n) => n.getAttribute('data-node-type') === 'endpointNode',
      )

      const nodeA = endpointNodes.find((n) => n.getAttribute('data-node-id') === 'ce-a')
      const nodeB = endpointNodes.find((n) => n.getAttribute('data-node-id') === 'ce-b')

      // treeOrder on node should match ce.tree_order from API
      expect(nodeA?.getAttribute('data-node-tree-order')).toBe('7')
      expect(nodeB?.getAttribute('data-node-tree-order')).toBe('3')
    })

    // Cleanup
    mockCanvasEndpointsData.length = 0
  })

  it('endpoint node treeOrder falls back to loop index when ce.tree_order is null', async () => {
    mockCanvasEndpointsData.length = 0
    mockCanvasEndpointsData.push({
      id: 'ce-null-order',
      canvas_id: 'canvas-1',
      endpoint_id: 'ep-1',
      parent_ref_id: null,
      field_role: 'primary',
      variable_extractions: null,
      max_concurrency: 1,
      tree_order: null,   // null → fallback to loop index 0
      exclusion_rules: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })

    mockBaseDetectionResult = { baseNodeId: null, hasIdentityFields: false }

    render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

    await waitFor(() => {
      const nodes = screen.getAllByTestId('rf-node')
      const epNode = nodes.find((n) => n.getAttribute('data-node-id') === 'ce-null-order')
      // Fallback to loop index 0 when tree_order is null
      expect(epNode?.getAttribute('data-node-tree-order')).toBe('0')
    })

    // Cleanup
    mockCanvasEndpointsData.length = 0
  })
})

// ---------------------------------------------------------------------------
// Gap 3 (UX-01): CanvasWarningBanner rendered with visible={!hasIdentityFields}
// ---------------------------------------------------------------------------

describe('UX-01: ChainCanvas renders CanvasWarningBanner with visible={!hasIdentityFields}', () => {
  it('passes visible=true to CanvasWarningBanner when no identity fields are mapped', async () => {
    const { useBaseDetection } = await import('@/hooks/useBaseDetection')
    vi.mocked(useBaseDetection).mockReturnValue({ baseNodeId: null, hasIdentityFields: false })
    capturedBannerVisible = undefined

    render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(screen.getByTestId('react-flow')).toBeInTheDocument()
    })

    // visible={!hasIdentityFields} = !false = true → banner rendered
    expect(capturedBannerVisible).toBe(true)
    expect(screen.getByTestId('canvas-warning-banner')).toBeInTheDocument()
  })

  it('passes visible=false to CanvasWarningBanner when identity fields are mapped', async () => {
    const { useBaseDetection } = await import('@/hooks/useBaseDetection')
    vi.mocked(useBaseDetection).mockReturnValue({ baseNodeId: 'ce-x', hasIdentityFields: true })
    capturedBannerVisible = undefined

    render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

    await waitFor(() => {
      expect(screen.getByTestId('react-flow')).toBeInTheDocument()
    })

    // visible={!hasIdentityFields} = !true = false → banner hidden
    expect(capturedBannerVisible).toBe(false)
    expect(screen.queryByTestId('canvas-warning-banner')).not.toBeInTheDocument()
  })
})
