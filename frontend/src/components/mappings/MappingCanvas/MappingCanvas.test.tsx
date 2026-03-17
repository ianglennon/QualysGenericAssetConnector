import { describe, it, vi, expect, beforeAll } from 'vitest'
import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SourcePanelNode } from './SourcePanelNode'
import { TargetPanelNode } from './TargetPanelNode'
import { applyConnect, normalizeConnection, isValidConnection, MappingCanvas } from './MappingCanvas'
import type { Edge, Connection } from '@xyflow/react'

// These stubs are RED until Plans 02 and 03 implement the components.
// They define the behavioral contracts upfront.

beforeAll(() => {
  class MockResizeObserver {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  global.ResizeObserver = MockResizeObserver as any
})

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

vi.mock('@/hooks/queries/useEndpointDiscover', () => ({
  useEndpointDiscoverFields: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}))

const mockSavedMappings = [
  {
    id: 'mapping-1',
    connector_id: 'conn-1',
    source_field: 'hostname',
    target_field: 'hostName',
    mapping_type: 'direct_copy',
    static_value: null,
    conditions: null,
    fallback: null,
    order: 0,
    created_at: '2026-01-01T00:00:00Z',
  },
]

vi.mock('@/hooks/queries/useEndpointMappings', () => ({
  useEndpointMappings: vi.fn(() => ({
    data: mockSavedMappings,
    isLoading: false,
    isError: false,
  })),
}))

vi.mock('@/hooks/queries/useQualysSchema', () => ({
  useQualysSchema: vi.fn(() => ({
    data: {
      fields: [
        { field: 'hostName', is_identity: true },
        { field: 'name', is_identity: false },
        { field: 'address', is_identity: false },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}))

// Stub ReactFlow to avoid canvas complexity in unit tests
// useEdgesState uses actual React.useState so setEdges calls update state and
// trigger the onEdgesSnapshot useEffect inside MappingCanvas.
vi.mock('@xyflow/react', async () => {
  const { useState } = await import('react')
  return {
    ReactFlow: ({ children }: { children?: React.ReactNode }) => (
      <div data-testid="react-flow">{children}</div>
    ),
    ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    useNodesState: () => [[], vi.fn(), vi.fn()],
    useEdgesState: (init: any) => {
      const [edges, setEdges] = useState(init ?? [])
      return [edges, setEdges, vi.fn()]
    },
    useReactFlow: () => ({ deleteElements: vi.fn() }),
    useUpdateNodeInternals: () => vi.fn(),
    useNodeId: () => 'source-panel',
    Handle: ({ id }: { id?: string }) => <div data-testid="handle" data-id={id} />,
    Position: { Left: 'left', Right: 'right' },
    BaseEdge: () => <path />,
    EdgeLabelRenderer: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    getSmoothStepPath: () => ['M0,0', 50, 50],
    Background: () => null,
    BackgroundVariant: { Dots: 'dots' },
    addEdge: vi.fn((edge: Connection, edges: Edge[]) => [...edges, edge as Edge]),
  }
})

const mockSourceFields = [
  { path: 'address.city', type: 'string', sample_value: 'Austin' },
  { path: 'hostname', type: 'string', sample_value: 'server-01' },
]

const mockTargetFields = [
  { field: 'hostName', is_identity: true },
  { field: 'name', is_identity: false },
  { field: 'address', is_identity: false },
]

const minimalNodeProps = {
  id: 'source-panel',
  type: 'sourcePanel',
  xPos: 0,
  yPos: 0,
  zIndex: 0,
  isConnectable: true,
  dragging: false,
  selected: false,
  draggable: false,
  selectable: false,
  deletable: false,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
}

describe('SourcePanelNode', () => {
  it('displays "Source Fields" header', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText('Source Fields')).toBeInTheDocument()
  })

  it('shows unlinked field paths', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText('hostname')).toBeInTheDocument()
    expect(screen.getByText('address.city')).toBeInTheDocument()
  })

  it('shows "Linked (0)" separator when no connections', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText(/Linked \(0\)/)).toBeInTheDocument()
  })

  it('shows "(no connections yet)" placeholder in empty linked zone', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText('(no connections yet)')).toBeInTheDocument()
  })

  it('moves field to linked zone when in linkedSourceFields', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set(['hostname']) }}
      />
    )
    expect(screen.getByText(/Linked \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/Unlinked \(1\)/)).toBeInTheDocument()
  })

  it('outer div does NOT have overflow-hidden (handles must be visible)', () => {
    const { container } = render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    const outerDiv = container.querySelector('.bg-card.border.rounded-lg')
    expect(outerDiv?.className).not.toContain('overflow-hidden')
  })
})

describe('TargetPanelNode', () => {
  it('displays "Qualys Target Fields" header', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText('Qualys Target Fields')).toBeInTheDocument()
  })

  it('identity fields (is_identity: true) sort to top of target panel', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    const items = screen.getAllByText(/hostName|name|address/)
    // hostName (identity) should appear before name and address
    const idxIdentity = items.findIndex(el => el.textContent?.includes('hostName'))
    const idxName = items.findIndex(el => el.textContent === 'name')
    const idxAddress = items.findIndex(el => el.textContent === 'address')
    expect(idxIdentity).toBeLessThan(idxName)
    expect(idxIdentity).toBeLessThan(idxAddress)
  })

  it('identity fields display star prefix', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText('★ hostName')).toBeInTheDocument()
  })

  it('identity fields display [IDENTITY] badge', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText('[IDENTITY]')).toBeInTheDocument()
  })

  it('shows "Linked (0)" separator on empty canvas', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText(/Linked \(0\)/)).toBeInTheDocument()
  })

  it('outer div does NOT have overflow-hidden (handles must be visible)', () => {
    const { container } = render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    const outerDiv = container.querySelector('.bg-card.border.rounded-lg')
    expect(outerDiv?.className).not.toContain('overflow-hidden')
  })
})

describe('MappingCanvas', () => {
  it('renders canvas shell without crashing', () => {
    render(<MappingCanvas connectorId="conn-1" endpointId="ep-1" />, { wrapper: makeWrapper() })
    expect(screen.getByTestId('react-flow')).toBeInTheDocument()
  })

  it('linked/unlinked separator shows correct count after connection is added', async () => {
    // Edge seeding defers setEdges via double-rAF (so handles register first).
    // Make rAF synchronous so the chain completes within a single act() flush.
    const origRAF = globalThis.requestAnimationFrame
    globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => { cb(performance.now()); return 0 }) as typeof requestAnimationFrame
    try {
      const onEdgesSnapshot = vi.fn()
      render(
        <MappingCanvas connectorId="conn-1" endpointId="ep-1" onEdgesSnapshot={onEdgesSnapshot} />,
        { wrapper: makeWrapper() }
      )
      await act(async () => { await new Promise(r => setTimeout(r, 0)) })

      const lastCall = onEdgesSnapshot.mock.calls[onEdgesSnapshot.mock.calls.length - 1]
      expect(lastCall[0]).toHaveLength(1)
      expect(lastCall[0][0].sourceHandle).toBe('hostname')
      expect(lastCall[0][0].targetHandle).toBe('hostName')
    } finally {
      globalThis.requestAnimationFrame = origRAF
    }
  })

  it('breaking a connection returns fields to unlinked zone', async () => {
    // Override to return no saved mappings (simulates all connections removed)
    const { useEndpointMappings } = await import('@/hooks/queries/useEndpointMappings')
    vi.mocked(useEndpointMappings).mockReturnValue({ data: [], isLoading: false } as any)

    const onEdgesSnapshot = vi.fn()
    render(
      <MappingCanvas connectorId="conn-1" endpointId="ep-1" onEdgesSnapshot={onEdgesSnapshot} />,
      { wrapper: makeWrapper() }
    )
    await waitFor(() => expect(onEdgesSnapshot).toHaveBeenCalled())
    const lastEdges = onEdgesSnapshot.mock.calls[onEdgesSnapshot.mock.calls.length - 1][0]
    expect(lastEdges).toHaveLength(0)
  })

  it('canvas-prepopulate: onEdgesSnapshot prop is called on render', () => {
    const onEdgesSnapshot = vi.fn()
    render(
      <MappingCanvas connectorId="conn-1" endpointId="ep-1" onEdgesSnapshot={onEdgesSnapshot} />,
      { wrapper: makeWrapper() }
    )
    // onEdgesSnapshot should be called (via useEffect on edges changes)
    expect(onEdgesSnapshot).toHaveBeenCalled()
  })

  it('restores saved mappings after unmount and remount (navigate away & back)', async () => {
    // Restore mock in case a prior test changed it
    const { useEndpointMappings } = await import('@/hooks/queries/useEndpointMappings')
    vi.mocked(useEndpointMappings).mockReturnValue({ data: mockSavedMappings, isLoading: false } as any)

    const origRAF = globalThis.requestAnimationFrame
    globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      cb(performance.now()); return 0
    }) as typeof requestAnimationFrame
    try {
      const onEdgesSnapshot = vi.fn()

      // First mount — edges should be seeded from savedMappings
      const { unmount } = render(
        <MappingCanvas connectorId="conn-1" endpointId="ep-1" onEdgesSnapshot={onEdgesSnapshot} />,
        { wrapper: makeWrapper() }
      )
      await act(async () => { await new Promise(r => setTimeout(r, 0)) })

      let lastCall = onEdgesSnapshot.mock.calls[onEdgesSnapshot.mock.calls.length - 1]
      expect(lastCall[0]).toHaveLength(1)
      expect(lastCall[0][0].sourceHandle).toBe('hostname')

      // Navigate away (unmount)
      unmount()

      // Navigate back (remount) — edges should be re-seeded
      onEdgesSnapshot.mockClear()
      render(
        <MappingCanvas connectorId="conn-1" endpointId="ep-1" onEdgesSnapshot={onEdgesSnapshot} />,
        { wrapper: makeWrapper() }
      )
      await act(async () => { await new Promise(r => setTimeout(r, 0)) })

      lastCall = onEdgesSnapshot.mock.calls[onEdgesSnapshot.mock.calls.length - 1]
      expect(lastCall[0]).toHaveLength(1)
      expect(lastCall[0][0].sourceHandle).toBe('hostname')
      expect(lastCall[0][0].targetHandle).toBe('hostName')
    } finally {
      globalThis.requestAnimationFrame = origRAF
    }
  })

  it('shows skeleton while mappings are loading (cache miss)', async () => {
    const { useEndpointMappings } = await import('@/hooks/queries/useEndpointMappings')
    const mockHook = vi.mocked(useEndpointMappings)
    mockHook.mockReturnValue({ data: undefined, isLoading: true, isError: false } as any)

    const { container } = render(
      <MappingCanvas connectorId="conn-1" endpointId="ep-1" />,
      { wrapper: makeWrapper() }
    )
    // Should show skeleton, not the empty-state overlay
    expect(container.querySelector('[data-testid="react-flow"]')).toBeNull()

    // Restore mock
    mockHook.mockReturnValue({ data: mockSavedMappings, isLoading: false, isError: false } as any)
  })
})

describe('normalizeConnection', () => {
  it('passes through connection already in source→target order', () => {
    const conn: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'name',
    }
    expect(normalizeConnection(conn)).toEqual(conn)
  })

  it('swaps inverted target→source connection to source→target', () => {
    const conn: Connection = {
      source: 'target-panel',
      target: 'source-panel',
      sourceHandle: 'name',
      targetHandle: 'hostname',
    }
    const result = normalizeConnection(conn)
    expect(result.source).toBe('source-panel')
    expect(result.target).toBe('target-panel')
    expect(result.sourceHandle).toBe('hostname')
    expect(result.targetHandle).toBe('name')
  })
})

describe('connection logic', () => {
  it('applyConnect adds edge with mappingType=direct', () => {
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'address.city',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [])
    expect(result).toHaveLength(1)
    expect((result[0] as any).data?.mappingType).toBe('direct')
  })

  it('applyConnect replaces existing edge from same source handle', () => {
    const existing: Edge = {
      id: '1',
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'name',
      data: { mappingType: 'direct' },
    }
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [existing])
    expect(result).toHaveLength(1)
    expect((result[0] as any).data?.mappingType).toBe('direct')
    expect(result[0].targetHandle).toBe('address')
  })

  it('applyConnect replaces existing edge to same target handle', () => {
    const existing: Edge = {
      id: '2',
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'address',
      data: { mappingType: 'direct' },
    }
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'address.city',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [existing])
    expect(result).toHaveLength(1)
    expect(result[0].sourceHandle).toBe('address.city')
  })

  it('applyConnect preserves unrelated edges (no overwrite)', () => {
    const existing: Edge = {
      id: '1',
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'name',
      data: { mappingType: 'direct' },
    }
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'address.city',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [existing])
    expect(result).toHaveLength(2)
    expect(result.find(e => e.sourceHandle === 'hostname')).toBeTruthy()
    expect(result.find(e => e.sourceHandle === 'address.city')).toBeTruthy()
  })

  it('applyConnect normalizes inverted connection from target panel drag', () => {
    const connection: Connection = {
      source: 'target-panel',
      target: 'source-panel',
      sourceHandle: 'name',
      targetHandle: 'hostname',
    }
    const result = applyConnect(connection, [])
    expect(result).toHaveLength(1)
    expect(result[0].source).toBe('source-panel')
    expect(result[0].target).toBe('target-panel')
    expect(result[0].sourceHandle).toBe('hostname')
    expect(result[0].targetHandle).toBe('name')
  })

  it('isValidConnection returns false for self-loop (source === target)', () => {
    const connection: Connection = {
      source: 'source-panel',
      target: 'source-panel',
      sourceHandle: 'hostname',
      targetHandle: 'hostname',
    }
    expect(isValidConnection(connection)).toBe(false)
  })

  it('isValidConnection returns true for valid source→target connection', () => {
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'name',
    }
    expect(isValidConnection(connection)).toBe(true)
  })
})
