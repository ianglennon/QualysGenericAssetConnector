import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Edge } from '@xyflow/react'
import type { MappingEdgeData } from '@/types/canvas'
import { EndpointMappingsPage } from './EndpointMappingsPage'

// --- Module-level mocks ---

vi.mock('react-router-dom', () => ({
  useParams: vi.fn(() => ({ connectorId: 'conn-1', endpointId: 'ep-1' })),
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}))

vi.mock('@/hooks/queries/useConnectors', () => ({
  useConnector: vi.fn(() => ({
    data: { id: 'conn-1', name: 'Test Connector' },
    isLoading: false,
  })),
}))

vi.mock('@/hooks/queries/useEndpoints', () => ({
  useEndpoints: vi.fn(() => ({
    data: [{ id: 'ep-1', name: 'Devices', path: '/devices' }],
    isLoading: false,
  })),
}))

vi.mock('@/hooks/queries/useQualysSchema', () => ({
  useQualysSchema: vi.fn(() => ({
    data: {
      fields: [
        { field: 'instanceUuidSource', is_identity: true },
        { field: 'name', is_identity: false },
      ],
    },
  })),
}))

const mockMutateAsync = vi.fn().mockResolvedValue({
  replaced: 1,
  is_valid_mappings: true,
  validation_errors: [],
})

vi.mock('@/hooks/queries/useEndpointMappings', () => ({
  useEndpointMappings: vi.fn(() => ({ data: [], isLoading: false })),
  useBatchReplaceEndpointMappings: vi.fn(() => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  })),
}))

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

// Module-scoped injectable edge state — set per test in beforeEach
let _canvasEdges: Edge<MappingEdgeData>[] = []

vi.mock('@/components/mappings/MappingCanvas', () => ({
  MappingCanvas: ({ onEdgesSnapshot }: { onEdgesSnapshot?: (e: Edge<MappingEdgeData>[]) => void }) => {
    React.useEffect(() => {
      onEdgesSnapshot?.(_canvasEdges)
    }, [onEdgesSnapshot])
    return <div data-testid="mapping-canvas" />
  },
  ConfirmClearDialog: ({ open, onConfirm, onCancel }: { open: boolean; onConfirm: () => void; onCancel: () => void }) => {
    if (!open) return null
    return (
      <div data-testid="confirm-clear-dialog">
        <p>Remove all mappings for this endpoint? This cannot be undone.</p>
        <button onClick={onCancel}>Keep mappings</button>
        <button onClick={onConfirm}>Remove all mappings</button>
      </div>
    )
  },
}))

// --- QueryClient wrapper ---

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// --- Test fixtures ---

const directEdgeWithIdentity: Edge<MappingEdgeData>[] = [
  {
    id: 'e1',
    source: 'source-panel',
    sourceHandle: 'hostname',
    target: 'target-panel',
    targetHandle: 'instanceUuidSource',
    type: 'mapping',
    data: { mappingType: 'direct' },
  },
]

const staticEdgeUnconfigured: Edge<MappingEdgeData>[] = [
  ...directEdgeWithIdentity,
  {
    id: 'e2',
    source: 'source-panel',
    sourceHandle: 'address.city',
    target: 'target-panel',
    targetHandle: 'name',
    type: 'mapping',
    data: { mappingType: 'static', staticValue: '' },
  },
]

const conditionalEdgeUnconfigured: Edge<MappingEdgeData>[] = [
  ...directEdgeWithIdentity,
  {
    id: 'e3',
    source: 'source-panel',
    sourceHandle: 'address.city',
    target: 'target-panel',
    targetHandle: 'name',
    type: 'mapping',
    data: { mappingType: 'conditional', conditions: [] },
  },
]

// --- Tests ---

describe('EndpointMappingsPage', () => {
  beforeEach(() => {
    _canvasEdges = []
    mockMutateAsync.mockClear()
    mockToast.mockClear()
  })

  it('Save button is disabled when no identity field is linked', () => {
    _canvasEdges = []
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /save mappings/i })).toBeDisabled()
  })

  it('Save button is enabled when identity field is linked', () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /save mappings/i })).not.toBeDisabled()
  })

  it('Save button is disabled when static edge is unconfigured', () => {
    _canvasEdges = staticEdgeUnconfigured
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /save mappings/i })).toBeDisabled()
  })

  it('Save button is disabled when conditional edge is unconfigured', () => {
    _canvasEdges = conditionalEdgeUnconfigured
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /save mappings/i })).toBeDisabled()
  })

  it('clicking Save calls batchReplaceEndpointMappings with translated API types', async () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /save mappings/i }))
    await waitFor(() =>
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          connectorId: 'conn-1',
          endpointId: 'ep-1',
          mappings: expect.arrayContaining([
            expect.objectContaining({ mapping_type: 'direct_copy' }),
          ]),
        })
      )
    )
  })

  it('save success shows toast', async () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /save mappings/i }))
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Mappings saved' })
      )
    )
  })

  // --- Remove All flow tests ---

  it('Remove All button renders in the page', () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /remove all/i })).toBeInTheDocument()
  })

  it('Remove All button is disabled when no edges exist', () => {
    _canvasEdges = []
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /remove all/i })).toBeDisabled()
  })

  it('Remove All button is enabled when edges exist', () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /remove all/i })).not.toBeDisabled()
  })

  it('clicking Remove All opens ConfirmClearDialog', () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /remove all/i }))
    expect(screen.getByTestId('confirm-clear-dialog')).toBeInTheDocument()
  })

  it('confirming removal calls batchReplace with empty mappings', async () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /remove all/i }))
    fireEvent.click(screen.getByRole('button', { name: /remove all mappings/i }))
    await waitFor(() =>
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          connectorId: 'conn-1',
          endpointId: 'ep-1',
          mappings: [],
        })
      )
    )
  })

  it('successful removal shows All mappings removed toast', async () => {
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /remove all/i }))
    fireEvent.click(screen.getByRole('button', { name: /remove all mappings/i }))
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'All mappings removed' })
      )
    )
  })

  it('failed removal shows destructive toast', async () => {
    mockMutateAsync.mockRejectedValueOnce(new Error('Network error'))
    _canvasEdges = directEdgeWithIdentity
    render(<EndpointMappingsPage />, { wrapper: makeWrapper() })
    fireEvent.click(screen.getByRole('button', { name: /remove all/i }))
    fireEvent.click(screen.getByRole('button', { name: /remove all mappings/i }))
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to remove mappings',
          variant: 'destructive',
        })
      )
    )
  })
})
