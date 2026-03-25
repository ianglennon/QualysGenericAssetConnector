import { describe, it, vi, expect, beforeAll } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Activated against ChainCanvas from Plan 03.
// Behavioral contracts for CUI-01 and CUI-02.

beforeAll(() => {
  class MockResizeObserver {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  global.ResizeObserver = MockResizeObserver as any
})

// --- Mock react-router-dom ---
vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}))

// Captured callbacks for test access
const capturedCallbacks: {
  onConnectEnd: null | ((event: any, state: any) => void)
  isValidConnection: null | ((conn: any) => boolean)
} = {
  onConnectEnd: null,
  isValidConnection: null,
}

// --- Mock @xyflow/react ---
vi.mock('@xyflow/react', async () => {
  const { useState } = await import('react')

  // useNodesState as vi.fn so tests can spy on it / re-implement it
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
      capturedCallbacks.onConnectEnd = props.onConnectEnd ?? null
      capturedCallbacks.isValidConnection = props.isValidConnection ?? null
      return (
        <div data-testid="react-flow">
          {/* Render nodes as data attributes so tests can inspect them */}
          {(props.nodes ?? []).map((node: any) => (
            <div
              key={node.id}
              data-testid="rf-node"
              data-node-id={node.id}
              data-node-type={node.type}
              data-node-path={node.data?.path ?? ''}
              data-node-variable-extractions={
                node.data?.variableExtractions
                  ? JSON.stringify(node.data.variableExtractions)
                  : ''
              }
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

// Each mock hook returns a SINGLETON object so that === equality holds across renders,
// preventing the useEffect dependency from triggering on every re-render.
vi.mock('@/hooks/queries/useCanvases', () => {
  const canvases = { data: [{ id: 'canvas-1', connector_id: 'conn-1', name: 'Default Canvas' }], isLoading: false }
  const createCanvas = { mutate: vi.fn(), isPending: false, mutateAsync: vi.fn().mockResolvedValue({ id: 'canvas-new' }) }
  return {
    useCanvases: vi.fn(() => canvases),
    useCreateCanvas: vi.fn(() => createCanvas),
  }
})

vi.mock('@/hooks/queries/useCanvasEndpoints', () => {
  const canvasEndpoints = { data: [], isLoading: false }
  const createCE = { mutateAsync: vi.fn().mockResolvedValue({ id: 'ce-new' }), isPending: false }
  const updateCE = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
  const deleteCE = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
  return {
    useCanvasEndpoints: vi.fn(() => canvasEndpoints),
    useCreateCanvasEndpoint: vi.fn(() => createCE),
    useUpdateCanvasEndpoint: vi.fn(() => updateCE),
    useDeleteCanvasEndpoint: vi.fn(() => deleteCE),
  }
})

vi.mock('@/hooks/queries/useEndpoints', () => {
  const endpoints = { data: [], isLoading: false }
  const createEP = { mutateAsync: vi.fn().mockResolvedValue({ id: 'ep-new', name: 'New', path: '/new' }), isPending: false }
  return {
    useEndpoints: vi.fn(() => endpoints),
    useCreateEndpoint: vi.fn(() => createEP),
  }
})

vi.mock('@/hooks/queries/useEndpointDiscover', () => {
  const discover = { mutate: vi.fn(), isPending: false }
  return { useEndpointDiscoverFields: vi.fn(() => discover) }
})

vi.mock('@/hooks/queries/useEndpointMappings', () => {
  const batch = { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }
  return { useBatchReplaceEndpointMappings: vi.fn(() => batch) }
})

vi.mock('@/hooks/queries/useQualysSchema', () => {
  const schema = { data: { fields: [{ field: 'hostName', is_identity: true }, { field: 'name', is_identity: false }] }, isLoading: false }
  return { useQualysSchema: vi.fn(() => schema) }
})

vi.mock('@/hooks/use-toast', () => {
  const toastFn = vi.fn()
  return { useToast: vi.fn(() => ({ toast: toastFn })) }
})

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { fields: [] } }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    patch: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

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

describe('ChainCanvas', () => {
  describe('CUI-01: Parent endpoint selection via drag', () => {
    it('renders empty state when no endpoints exist', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

      await waitFor(() => {
        expect(screen.getByText('No endpoints on this canvas')).toBeInTheDocument()
      })
    })

    it('creates a new endpoint node when Create Endpoint is clicked', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

      const createButton = await screen.findByRole('button', { name: /Create Endpoint/i })
      await act(async () => {
        fireEvent.click(createButton)
      })

      // After creating a node, the empty state disappears
      await waitFor(() => {
        expect(screen.queryByText('No endpoints on this canvas')).not.toBeInTheDocument()
      })
    })

    it('opens context menu when field handle is dragged to empty canvas', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

      await waitFor(() => {
        expect(screen.getByTestId('react-flow')).toBeInTheDocument()
      })

      await act(async () => {
        capturedCallbacks.onConnectEnd?.(
          { clientX: 200, clientY: 300 },
          { isValid: false, fromNode: { id: 'node-parent' }, fromHandle: { id: 'hostname' } }
        )
      })

      await waitFor(() => {
        expect(screen.getByText('Create Child Endpoint')).toBeInTheDocument()
      })
    })

    it('creates child endpoint with chain edge when context menu item is selected', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

      await waitFor(() => {
        expect(screen.getByTestId('react-flow')).toBeInTheDocument()
      })

      await act(async () => {
        capturedCallbacks.onConnectEnd?.(
          { clientX: 300, clientY: 400 },
          { isValid: false, fromNode: { id: 'node-parent' }, fromHandle: { id: 'name' } }
        )
      })

      await waitFor(() => {
        expect(screen.getByText('Create Child Endpoint')).toBeInTheDocument()
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Create Child Endpoint'))
      })

      // Child was created: empty state is gone
      await waitFor(() => {
        expect(screen.queryByText('No endpoints on this canvas')).not.toBeInTheDocument()
      })
    })

    it('prevents cycle creation via isValidConnection', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })

      await waitFor(() => {
        expect(screen.getByTestId('react-flow')).toBeInTheDocument()
      })

      expect(typeof capturedCallbacks.isValidConnection).toBe('function')

      // Self-loop connections must be rejected
      expect(capturedCallbacks.isValidConnection!({ source: 'A', target: 'A' })).toBe(false)
    })
  })

  describe('CUI-02: Variable extraction auto-inferred from drag', () => {
    it('pre-fills child path with {fieldName} from dragged field', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })
      await waitFor(() => screen.getByTestId('react-flow'))

      // Simulate drag from field handle 'hostname' to empty canvas
      await act(async () => {
        capturedCallbacks.onConnectEnd?.(
          { clientX: 200, clientY: 200 },
          { isValid: false, fromNode: { id: 'node-parent' }, fromHandle: { id: 'hostname' } }
        )
      })

      await waitFor(() => screen.getByText('Create Child Endpoint'))

      await act(async () => {
        fireEvent.click(screen.getByText('Create Child Endpoint'))
      })

      // The ReactFlow mock renders each node as a data element with data-node-path
      // The child endpoint node should have path containing {hostname}
      await waitFor(() => {
        const nodes = screen.getAllByTestId('rf-node')
        const childNode = nodes.find(
          (el) =>
            el.getAttribute('data-node-type') === 'endpointNode' &&
            (el.getAttribute('data-node-path') ?? '').includes('{hostname}')
        )
        expect(childNode).toBeTruthy()
      })
    })

    it('auto-populates variable_extractions from chain edge connection', async () => {
      render(<ChainCanvas {...defaultProps} />, { wrapper: makeWrapper() })
      await waitFor(() => screen.getByTestId('react-flow'))

      // Simulate drag from field handle 'results.id' to empty canvas
      await act(async () => {
        capturedCallbacks.onConnectEnd?.(
          { clientX: 200, clientY: 200 },
          { isValid: false, fromNode: { id: 'node-parent' }, fromHandle: { id: 'results.id' } }
        )
      })

      await waitFor(() => screen.getByText('Create Child Endpoint'))

      await act(async () => {
        fireEvent.click(screen.getByText('Create Child Endpoint'))
      })

      // The ReactFlow mock serializes variableExtractions to a data attribute
      // Last segment of 'results.id' is 'id' — expect map { id: 'results.id' }
      await waitFor(() => {
        const nodes = screen.getAllByTestId('rf-node')
        const childNode = nodes.find(
          (el) =>
            el.getAttribute('data-node-type') === 'endpointNode' &&
            el.getAttribute('data-node-variable-extractions') !== ''
        )
        expect(childNode).toBeTruthy()
        const extractions = JSON.parse(
          childNode!.getAttribute('data-node-variable-extractions')!
        )
        expect(extractions).toHaveProperty('id', 'results.id')
      })
    })
  })
})
