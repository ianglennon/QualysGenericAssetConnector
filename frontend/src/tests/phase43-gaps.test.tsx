/**
 * Phase 43 gap-fill tests (frontend).
 *
 * Gap 5  — RunDetailPage renders chain logs indented, flat logs flat, fan-out summary
 * Gap 6  — SourcePanelNode groups _parent.* fields by ancestor depth
 * Gap 7  — EndpointMappingsPage shows parent gating banner
 * Gap 8  — CanvasToolbar shows dry-run button when canvas has chains
 * Gap 9  — DryRunResultsPage shows mapped records + cap notice
 * Gap 10 — useDryRun hook calls POST dry-run endpoint
 */

import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ─── shared test helpers ──────────────────────────────────────────────────────

function withRouter(ui: React.ReactElement, initialEntries = ['/']) {
  return <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
}

function withQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

function withAll(ui: React.ReactElement, initialEntries = ['/']) {
  return withQuery(withRouter(ui, initialEntries))
}

// ─── Gap 5: RunDetailPage chain logs indented, flat logs flat, fan-out summary ─

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: 'run-1' }),
  }
})

const mockUseRun = vi.fn()
vi.mock('@/hooks/queries/useRuns', () => ({
  useRun: (...args: unknown[]) => mockUseRun(...args),
  useRuns: vi.fn(() => ({ data: null, isLoading: false })),
  useTriggerRun: vi.fn(() => ({ mutate: vi.fn() })),
}))

describe('Gap 5: RunDetailPage chain log layout', () => {
  const makeRun = (logs: object[]) => ({
    id: 'run-1',
    connector_id: 'conn-1',
    connector_name: 'Test Connector',
    status: 'success',
    started_at: '2026-03-25T10:00:00Z',
    finished_at: '2026-03-25T10:01:00Z',
    records_fetched: 5,
    records_submitted: 5,
    records_failed: 0,
    error_message: null,
    endpoint_logs: logs,
  })

  const chainLog = {
    id: 'log-chain',
    run_id: 'run-1',
    endpoint_id: 'ep-1',
    endpoint_name: 'Child Endpoint',
    endpoint_path: '/api/children',
    execution_order: 1,
    records_fetched: 3,
    records_submitted: 3,
    records_failed: 0,
    status: 'success',
    error_message: undefined,
    failure_stage: null,
    created_at: '2026-03-25T10:00:00Z',
    canvas_id: 'canvas-1',
    child_requests_total: 4,
    child_requests_failed: 1,
    child_requests_skipped: 0,
    depth: 1,
  }

  const flatLog = {
    id: 'log-flat',
    run_id: 'run-1',
    endpoint_id: 'ep-2',
    endpoint_name: 'Flat Endpoint',
    endpoint_path: '/api/flat',
    execution_order: 0,
    records_fetched: 2,
    records_submitted: 2,
    records_failed: 0,
    status: 'success',
    error_message: undefined,
    failure_stage: null,
    created_at: '2026-03-25T10:00:00Z',
    canvas_id: null,
    depth: null,
  }

  it('renders fan-out summary line for chain log with child_requests_total > 0', async () => {
    const { default: RunDetailPage } = await import('@/pages/RunHistory/RunDetailPage')
    mockUseRun.mockReturnValue({ data: makeRun([chainLog]), isLoading: false })

    render(withRouter(<RunDetailPage />))

    // Fan-out summary should be present: "{succeeded}/{total} children succeeded"
    expect(screen.getByText(/children succeeded/)).toBeDefined()
  })

  it('renders failed count in fan-out summary when child_requests_failed > 0', async () => {
    const { default: RunDetailPage } = await import('@/pages/RunHistory/RunDetailPage')
    mockUseRun.mockReturnValue({ data: makeRun([chainLog]), isLoading: false })

    render(withRouter(<RunDetailPage />))

    // "1 failed" should appear inside the fan-out paragraph
    expect(screen.getByText(/1 failed/)).toBeDefined()
  })

  it('does not render fan-out summary for flat (non-chain) logs', async () => {
    const { default: RunDetailPage } = await import('@/pages/RunHistory/RunDetailPage')
    mockUseRun.mockReturnValue({ data: makeRun([flatLog]), isLoading: false })

    render(withRouter(<RunDetailPage />))

    expect(screen.queryByText(/children succeeded/)).toBeNull()
  })

  it('renders empty state text when no endpoint logs present', async () => {
    const { default: RunDetailPage } = await import('@/pages/RunHistory/RunDetailPage')
    mockUseRun.mockReturnValue({ data: makeRun([]), isLoading: false })

    render(withRouter(<RunDetailPage />))

    expect(screen.getByText('No endpoint logs recorded for this run.')).toBeDefined()
  })
})

// ─── Gap 6: SourcePanelNode groups _parent.* fields ──────────────────────────

// React Flow mock required for SourcePanelNode
vi.mock('@xyflow/react', async () => {
  const { useState, useEffect } = await import('react')
  return {
    useUpdateNodeInternals: () => vi.fn(),
    useNodeId: () => 'source-panel',
    Handle: ({ id }: { id: string }) => <span data-testid={`handle-${id}`} />,
    Position: { Right: 'right', Left: 'left' },
    ReactFlow: ({ children }: any) => <div data-testid="react-flow">{children}</div>,
    ReactFlowProvider: ({ children }: any) => <>{children}</>,
    useNodesState: (init: any[] = []) => {
      const [nodes, setNodes] = useState(init)
      return [nodes, setNodes, vi.fn()]
    },
    useEdgesState: (init: any[] = []) => {
      const [edges, setEdges] = useState(init)
      return [edges, setEdges, vi.fn()]
    },
    useReactFlow: () => ({
      screenToFlowPosition: (pos: any) => pos,
      getNode: () => null,
      fitView: vi.fn(),
    }),
    Background: () => <div />,
    BackgroundVariant: { Dots: 'dots' },
  }
})

describe('Gap 6: SourcePanelNode ancestor field grouping', () => {
  it('renders "Parent Fields" section header for _parent.* fields at depth 1', async () => {
    const { SourcePanelNode } = await import(
      '@/components/mappings/MappingCanvas/SourcePanelNode'
    )

    const data = {
      fields: [
        { path: 'name', type: 'string', sample_value: 'server-1' },
        { path: '_parent.id', type: 'string', sample_value: 'dev-1' },
      ],
      linkedSourceFields: new Set<string>(),
      linkedFieldOrder: new Map<string, number>(),
    }

    render(<SourcePanelNode data={data} id="source-panel" type="sourcePanelNode" selected={false} />)

    // "Parent Fields" label appears in separator text (once for Linked, once for Unlinked)
    const matches = screen.getAllByText(/Parent Fields/)
    expect(matches.length).toBeGreaterThan(0)
  })

  it('renders "Grandparent Fields" section header for _parent._parent.* fields at depth 2', async () => {
    const { SourcePanelNode } = await import(
      '@/components/mappings/MappingCanvas/SourcePanelNode'
    )

    const data = {
      fields: [
        { path: '_parent._parent.id', type: 'string', sample_value: 'gp-1' },
      ],
      linkedSourceFields: new Set<string>(),
      linkedFieldOrder: new Map<string, number>(),
    }

    render(<SourcePanelNode data={data} id="source-panel" type="sourcePanelNode" selected={false} />)

    const matches = screen.getAllByText(/Grandparent Fields/)
    expect(matches.length).toBeGreaterThan(0)
  })

  it('does not show "Parent Fields" label when no _parent.* fields present', async () => {
    const { SourcePanelNode } = await import(
      '@/components/mappings/MappingCanvas/SourcePanelNode'
    )

    const data = {
      fields: [
        { path: 'name', type: 'string', sample_value: 'server-1' },
        { path: 'ip', type: 'string', sample_value: '10.0.0.1' },
      ],
      linkedSourceFields: new Set<string>(),
      linkedFieldOrder: new Map<string, number>(),
    }

    render(<SourcePanelNode data={data} id="source-panel" type="sourcePanelNode" selected={false} />)

    expect(screen.queryByText(/Parent Fields/)).toBeNull()
  })
})

// ─── Gap 7: EndpointMappingsPage parent gating banner ────────────────────────

// Set up mocks for EndpointMappingsPage
vi.mock('@/hooks/queries/useConnectors', () => ({
  useConnector: vi.fn(() => ({ data: { id: 'conn-1', name: 'My Connector' }, isLoading: false })),
}))

vi.mock('@/hooks/queries/useEndpoints', () => ({
  useEndpoints: vi.fn(() => ({
    data: [
      { id: 'ep-parent', name: 'Parent Endpoint', path: '/api/devices' },
      { id: 'ep-child', name: 'Child Endpoint', path: '/api/devices/{id}/ports' },
    ],
    isLoading: false,
  })),
  useCreateEndpoint: vi.fn(() => ({ mutateAsync: vi.fn() })),
}))

vi.mock('@/hooks/queries/useQualysSchema', () => ({
  useQualysSchema: vi.fn(() => ({
    data: { fields: [{ field: 'hostName', is_identity: true }] },
  })),
}))

vi.mock('@/hooks/queries/useEndpointMappings', () => ({
  useEndpointMappings: vi.fn(() => ({ data: [], isLoading: false })),
  useBatchReplaceEndpointMappings: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: vi.fn() })),
}))

const mockUseCanvases = vi.fn()
const mockUseCanvasEndpoints = vi.fn()
vi.mock('@/hooks/queries/useCanvases', () => ({
  useCanvases: (...args: unknown[]) => mockUseCanvases(...args),
  useCreateCanvas: vi.fn(() => ({ mutate: vi.fn() })),
}))

vi.mock('@/hooks/queries/useCanvasEndpoints', () => ({
  useCanvasEndpoints: (...args: unknown[]) => mockUseCanvasEndpoints(...args),
  useCreateCanvasEndpoint: vi.fn(() => ({ mutateAsync: vi.fn() })),
  useUpdateCanvasEndpoint: vi.fn(() => ({ mutateAsync: vi.fn() })),
}))

vi.mock('@/components/mappings/MappingCanvas', () => ({
  MappingCanvas: () => <div data-testid="mapping-canvas" />,
  ConfirmClearDialog: () => null,
}))

// Stub useParams for EndpointMappingsPage tests — points to the parent endpoint
const mockUseParamsForMappings = vi.fn(() => ({ connectorId: 'conn-1', endpointId: 'ep-parent' }))

describe('Gap 7: EndpointMappingsPage parent gating banner', () => {
  beforeAll(() => {
    // Canvas with one parent endpoint and one child referencing it
    mockUseCanvases.mockReturnValue({
      data: [{ id: 'canvas-1', connector_id: 'conn-1', name: 'Canvas' }],
    })
    mockUseCanvasEndpoints.mockReturnValue({
      data: [
        { id: 'ce-parent', endpoint_id: 'ep-parent', canvas_id: 'canvas-1', parent_ref_id: null },
        { id: 'ce-child', endpoint_id: 'ep-child', canvas_id: 'canvas-1', parent_ref_id: 'ce-parent' },
      ],
    })
  })

  it('shows "Data Source Endpoint" banner for a parent endpoint instead of canvas', async () => {
    // Override useParams to return the parent endpoint
    const { useParams } = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
    // Re-mock useParams with parent endpoint context
    vi.doMock('react-router-dom', async () => {
      const actual = await vi.importActual('react-router-dom')
      return { ...actual, useParams: () => ({ connectorId: 'conn-1', endpointId: 'ep-parent' }) }
    })

    const { EndpointMappingsPage } = await import('@/pages/Connectors/EndpointMappingsPage')
    render(withAll(<EndpointMappingsPage />))

    // The gating banner title should be present
    expect(screen.getByText('Data Source Endpoint')).toBeDefined()
  })

  it('shows child endpoint link inside the parent gating banner', async () => {
    vi.doMock('react-router-dom', async () => {
      const actual = await vi.importActual('react-router-dom')
      return { ...actual, useParams: () => ({ connectorId: 'conn-1', endpointId: 'ep-parent' }) }
    })

    const { EndpointMappingsPage } = await import('@/pages/Connectors/EndpointMappingsPage')
    render(withAll(<EndpointMappingsPage />))

    // Child endpoint name must appear as a link in the banner
    expect(screen.getByText('Child Endpoint')).toBeDefined()
  })

  it('hides Save and Remove buttons when endpoint is a parent', async () => {
    vi.doMock('react-router-dom', async () => {
      const actual = await vi.importActual('react-router-dom')
      return { ...actual, useParams: () => ({ connectorId: 'conn-1', endpointId: 'ep-parent' }) }
    })

    const { EndpointMappingsPage } = await import('@/pages/Connectors/EndpointMappingsPage')
    render(withAll(<EndpointMappingsPage />))

    expect(screen.queryByText('Save Mappings')).toBeNull()
    expect(screen.queryByText('Remove All')).toBeNull()
  })
})

// ─── Gap 8: CanvasToolbar shows dry-run button when hasChain=true ──────────────

describe('Gap 8: CanvasToolbar dry-run button', () => {
  it('renders "Run Dry Test" button when hasChain is true and onDryRun is provided', async () => {
    const { CanvasToolbar } = await import('@/components/canvas/CanvasToolbar')

    const onDryRun = vi.fn()
    render(
      withRouter(
        <CanvasToolbar
          onCreateEndpoint={vi.fn()}
          onAutoLayout={vi.fn()}
          onSave={vi.fn()}
          isSaving={false}
          canSave={true}
          connectorName="Test Connector"
          connectorId="conn-1"
          hasChain={true}
          onDryRun={onDryRun}
          isDryRunning={false}
        />
      )
    )

    expect(screen.getByText('Run Dry Test')).toBeDefined()
  })

  it('does not render "Run Dry Test" button when hasChain is false', async () => {
    const { CanvasToolbar } = await import('@/components/canvas/CanvasToolbar')

    render(
      withRouter(
        <CanvasToolbar
          onCreateEndpoint={vi.fn()}
          onAutoLayout={vi.fn()}
          onSave={vi.fn()}
          isSaving={false}
          canSave={true}
          connectorName="Test Connector"
          connectorId="conn-1"
          hasChain={false}
          onDryRun={vi.fn()}
          isDryRunning={false}
        />
      )
    )

    expect(screen.queryByText('Run Dry Test')).toBeNull()
  })

  it('does not render "Run Dry Test" button when onDryRun is not provided', async () => {
    const { CanvasToolbar } = await import('@/components/canvas/CanvasToolbar')

    render(
      withRouter(
        <CanvasToolbar
          onCreateEndpoint={vi.fn()}
          onAutoLayout={vi.fn()}
          onSave={vi.fn()}
          isSaving={false}
          canSave={true}
          connectorName="Test Connector"
          connectorId="conn-1"
          hasChain={true}
          // onDryRun intentionally omitted
          isDryRunning={false}
        />
      )
    )

    expect(screen.queryByText('Run Dry Test')).toBeNull()
  })
})

// ─── Gap 9: DryRunResultsPage shows mapped records + cap notice ───────────────

describe('Gap 9: DryRunResultsPage renders results and cap notice', () => {
  it('renders mapped records in a table with column headers', async () => {
    const { DryRunResultsPage } = await import('@/pages/Connectors/DryRunResultsPage')

    const state = {
      dryRunResults: {
        records: [{ hostName: 'server-1', ip: '10.0.0.1' }],
        total_records: 1,
        capped: false,
      },
    }

    render(
      <MemoryRouter
        initialEntries={[{ pathname: '/connectors/conn-1/canvases/canvas-1/dry-run-results', state }]}
      >
        <DryRunResultsPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Dry Run Results')).toBeDefined()
    // Column headers derived from record keys
    expect(screen.getByText('hostName')).toBeDefined()
    expect(screen.getByText('ip')).toBeDefined()
    // Record value
    expect(screen.getByText('server-1')).toBeDefined()
  })

  it('shows cap notice "Showing 50 of N total records" when capped=true', async () => {
    const { DryRunResultsPage } = await import('@/pages/Connectors/DryRunResultsPage')

    const state = {
      dryRunResults: {
        records: [{ hostName: 'server-1' }],
        total_records: 75,
        capped: true,
      },
    }

    render(
      <MemoryRouter
        initialEntries={[{ pathname: '/connectors/conn-1/canvases/canvas-1/dry-run-results', state }]}
      >
        <DryRunResultsPage />
      </MemoryRouter>
    )

    expect(screen.getByText(/Showing 50 of 75 total records/)).toBeDefined()
  })

  it('shows "No Records" state when result.records is empty', async () => {
    const { DryRunResultsPage } = await import('@/pages/Connectors/DryRunResultsPage')

    const state = {
      dryRunResults: {
        records: [],
        total_records: 0,
        capped: false,
      },
    }

    render(
      <MemoryRouter
        initialEntries={[{ pathname: '/connectors/conn-1/canvases/canvas-1/dry-run-results', state }]}
      >
        <DryRunResultsPage />
      </MemoryRouter>
    )

    expect(screen.getByText('No Records')).toBeDefined()
  })

  it('shows "No Results Available" when no location.state is provided', async () => {
    const { DryRunResultsPage } = await import('@/pages/Connectors/DryRunResultsPage')

    render(
      <MemoryRouter
        initialEntries={['/connectors/conn-1/canvases/canvas-1/dry-run-results']}
      >
        <DryRunResultsPage />
      </MemoryRouter>
    )

    expect(screen.getByText('No Results Available')).toBeDefined()
  })
})

// ─── Gap 10: useDryRun hook calls POST dry-run endpoint ──────────────────────

const mockApiPost = vi.fn()
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    post: (...args: unknown[]) => mockApiPost(...args),
    get: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

describe('Gap 10: useDryRun hook calls POST dry-run endpoint', () => {
  it('calls POST /connectors/{id}/canvases/{canvasId}/dry-run with correct URL', async () => {
    const { renderHook } = await import('@testing-library/react')
    const { useDryRun } = await import('@/hooks/queries/useDryRun')

    const expectedResult = { records: [], total_records: 0, capped: false }
    mockApiPost.mockResolvedValueOnce({ data: expectedResult })

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useDryRun(), { wrapper })

    await result.current.mutateAsync({ connectorId: 'conn-1', canvasId: 'canvas-abc' })

    expect(mockApiPost).toHaveBeenCalledWith('/connectors/conn-1/canvases/canvas-abc/dry-run')
  })

  it('returns DryRunResult data from the API response', async () => {
    const { renderHook, act } = await import('@testing-library/react')
    const { useDryRun } = await import('@/hooks/queries/useDryRun')

    const apiResult = {
      records: [{ hostName: 'server-1' }],
      total_records: 1,
      capped: false,
    }
    mockApiPost.mockResolvedValueOnce({ data: apiResult })

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useDryRun(), { wrapper })

    let returned: unknown
    await act(async () => {
      returned = await result.current.mutateAsync({ connectorId: 'conn-1', canvasId: 'canvas-abc' })
    })

    expect(returned).toEqual(apiResult)
  })
})
