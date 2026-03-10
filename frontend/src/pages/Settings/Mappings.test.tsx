import { describe, it, vi, expect, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Mappings from './Mappings'
import type { Edge } from '@xyflow/react'
import type { MappingEdgeData } from '@/types/canvas'

// Mock connector data
const mockConnectors = [
  { id: 'conn-1', name: 'Test Connector', base_url: 'http://example.com', auth_method: 'bearer_token' as const, has_token: true, has_username: false, has_password: false, has_api_key: false, pagination_strategies: [], created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
]

// Mock schema data with one identity field
const mockSchemaData = {
  fields: [
    { field: 'instanceUuidSource', is_identity: true },
    { field: 'name', is_identity: false },
  ],
}

// Edges for testing
const directEdgeWithIdentity: Edge<MappingEdgeData>[] = [
  {
    id: 'e1',
    source: 'source-panel',
    sourceHandle: 'hostname',
    target: 'target-panel',
    targetHandle: 'instanceUuidSource',
    data: { mappingType: 'direct' },
  },
]

const staticEdgeUnconfigured: Edge<MappingEdgeData>[] = [
  {
    id: 'e1',
    source: 'source-panel',
    sourceHandle: 'hostname',
    target: 'target-panel',
    targetHandle: 'instanceUuidSource',
    data: { mappingType: 'static', staticValue: '' },
  },
]

const staticEdgeConfigured: Edge<MappingEdgeData>[] = [
  {
    id: 'e1',
    source: 'source-panel',
    sourceHandle: 'hostname',
    target: 'target-panel',
    targetHandle: 'instanceUuidSource',
    data: { mappingType: 'static', staticValue: 'hello' },
  },
]

const conditionalEdgeUnconfigured: Edge<MappingEdgeData>[] = [
  {
    id: 'e1',
    source: 'source-panel',
    sourceHandle: 'hostname',
    target: 'target-panel',
    targetHandle: 'instanceUuidSource',
    data: { mappingType: 'conditional', conditions: [] },
  },
]

// Canvas edges to inject via mock
let _canvasEdges: Edge<MappingEdgeData>[] = []

vi.mock('@/hooks/queries/useConnectors', () => ({
  useConnectors: vi.fn(() => ({
    data: mockConnectors,
    isLoading: false,
  })),
}))

vi.mock('@/hooks/queries/useQualysSchema', () => ({
  useQualysSchema: vi.fn(() => ({
    data: mockSchemaData,
    isLoading: false,
  })),
}))

const mockMutateAsync = vi.fn().mockResolvedValue({ replaced: 1, is_valid_mappings: true, validation_errors: [] })
const mockBatchReplace = { mutateAsync: mockMutateAsync, isPending: false }

vi.mock('@/hooks/queries/useMappings', () => ({
  useMappings: vi.fn(() => ({ data: [], isLoading: false })),
  useBatchReplaceMappings: vi.fn(() => mockBatchReplace),
}))

// Mock MappingCanvas — calls onEdgesSnapshot with test edges
vi.mock('@/components/mappings/MappingCanvas', () => ({
  MappingCanvas: ({ onEdgesSnapshot }: { onEdgesSnapshot?: (e: Edge<MappingEdgeData>[]) => void }) => {
    // Call onEdgesSnapshot with the injected edges
    React.useEffect(() => {
      onEdgesSnapshot?.(_canvasEdges)
    }, [onEdgesSnapshot])
    return <div data-testid="mapping-canvas" />
  },
  ConfirmClearDialog: ({ open, onConfirm, onCancel }: { open: boolean; onConfirm: () => void; onCancel: () => void }) => {
    if (!open) return null
    return (
      <div data-testid="confirm-clear-dialog">
        <button onClick={onConfirm} data-testid="confirm-btn">Confirm</button>
        <button onClick={onCancel} data-testid="cancel-btn">Cancel</button>
      </div>
    )
  },
}))

vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({
    toast: vi.fn(),
  })),
  toast: vi.fn(),
}))

// Helper to render Mappings with a selected connector
async function renderMappingsWithConnector() {
  render(<Mappings />)
  // Select the connector from the select dropdown
  const trigger = screen.getByRole('combobox')
  fireEvent.click(trigger)
  const option = await screen.findByText('Test Connector')
  fireEvent.click(option)
  return screen
}

beforeEach(() => {
  _canvasEdges = []
  mockMutateAsync.mockClear()
  mockMutateAsync.mockResolvedValue({ replaced: 1, is_valid_mappings: true, validation_errors: [] })
})

describe('Mappings page save gate', () => {
  it('Save button is disabled when no identity attribute is linked', async () => {
    _canvasEdges = []
    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    expect(saveBtn).toBeDisabled()
  })

  it('Save button is disabled when a static widget has no staticValue', async () => {
    _canvasEdges = staticEdgeUnconfigured
    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    expect(saveBtn).toBeDisabled()
  })

  it('Save button is disabled when a conditional widget has empty conditions', async () => {
    _canvasEdges = conditionalEdgeUnconfigured
    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    expect(saveBtn).toBeDisabled()
  })

  it('Save button is enabled when identity linked and all widgets configured', async () => {
    _canvasEdges = directEdgeWithIdentity
    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    expect(saveBtn).not.toBeDisabled()
  })
})

describe('Mappings page save flow', () => {
  it('save handler calls PUT batch-replace with canvas-to-API type translation', async () => {
    _canvasEdges = directEdgeWithIdentity
    const { useToast } = await import('@/hooks/use-toast')
    const mockToast = vi.fn()
    vi.mocked(useToast).mockReturnValue({ toast: mockToast, toasts: [], dismiss: vi.fn() })

    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        connectorId: 'conn-1',
        mappings: expect.arrayContaining([
          expect.objectContaining({
            mapping_type: 'direct_copy',
            source_field: 'hostname',
            target_field: 'instanceUuidSource',
          }),
        ]),
      })
    })
  })

  it('save success shows toast notification', async () => {
    _canvasEdges = directEdgeWithIdentity
    const { useToast } = await import('@/hooks/use-toast')
    const mockToast = vi.fn()
    vi.mocked(useToast).mockReturnValue({ toast: mockToast, toasts: [], dismiss: vi.fn() })

    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Mappings saved' })
      )
    })
  })

  it('save error shows error toast notification', async () => {
    _canvasEdges = directEdgeWithIdentity
    mockMutateAsync.mockRejectedValueOnce(new Error('Network error'))

    const { useToast } = await import('@/hooks/use-toast')
    const mockToast = vi.fn()
    vi.mocked(useToast).mockReturnValue({ toast: mockToast, toasts: [], dismiss: vi.fn() })

    await renderMappingsWithConnector()
    const saveBtn = screen.getByRole('button', { name: /save mappings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to save mappings', variant: 'destructive' })
      )
    })
  })
})

describe('Mappings page remove-all flow', () => {
  it('Remove all button opens ConfirmClearDialog', async () => {
    _canvasEdges = directEdgeWithIdentity
    await renderMappingsWithConnector()

    const removeBtn = screen.getByRole('button', { name: /remove all/i })
    fireEvent.click(removeBtn)

    expect(screen.getByTestId('confirm-clear-dialog')).toBeInTheDocument()
  })

  it('Confirm in dialog calls batch-replace with empty array', async () => {
    _canvasEdges = directEdgeWithIdentity
    await renderMappingsWithConnector()

    const removeBtn = screen.getByRole('button', { name: /remove all/i })
    fireEvent.click(removeBtn)

    const confirmBtn = screen.getByTestId('confirm-btn')
    fireEvent.click(confirmBtn)

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        connectorId: 'conn-1',
        mappings: [],
      })
    })
  })

  it('Cancel in dialog does not call API', async () => {
    _canvasEdges = directEdgeWithIdentity
    await renderMappingsWithConnector()

    const removeBtn = screen.getByRole('button', { name: /remove all/i })
    fireEvent.click(removeBtn)

    const cancelBtn = screen.getByTestId('cancel-btn')
    fireEvent.click(cancelBtn)

    expect(mockMutateAsync).not.toHaveBeenCalled()
    expect(screen.queryByTestId('confirm-clear-dialog')).not.toBeInTheDocument()
  })
})
