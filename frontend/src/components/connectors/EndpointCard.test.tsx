/**
 * DEL-06: Endpoint deletion 409 response shows actionable toast with canvas names.
 * When DELETE endpoint returns 409 ENDPOINT_IN_USE, EndpointCard must display a
 * destructive toast listing the canvas names from the error response.
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ConnectorEndpoint } from '@/types/api'

// --- Mocks ---

vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) =>
    React.createElement('a', { href: to }, children),
}))

vi.mock('@dnd-kit/sortable', () => ({
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    transition: null,
    isDragging: false,
  }),
}))

vi.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } },
}))

vi.mock('@/routes/constants', () => ({
  ROUTES: {
    connectorMappings: (connId: string, epId: string) =>
      `/connectors/${connId}/endpoints/${epId}/mappings`,
  },
}))

const mockUpdateMutate = vi.fn()
vi.mock('@/hooks/queries/useEndpoints', () => ({
  useUpdateEndpoint: vi.fn(() => ({
    mutate: mockUpdateMutate,
    isPending: false,
  })),
  useDeleteEndpoint: vi.fn(() => ({
    mutate: mockDeleteMutate,
    isPending: false,
  })),
}))

// Forward reference for delete mock (defined after vi.mock hoisting)
let mockDeleteMutate: ReturnType<typeof vi.fn>

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

// Reinitialise mockDeleteMutate after vi.mock hoisting
mockDeleteMutate = vi.fn()

// Re-assign via module re-import after mock setup
import { useDeleteEndpoint } from '@/hooks/queries/useEndpoints'
import { EndpointCard } from './EndpointCard'

const testEndpoint: ConnectorEndpoint = {
  id: 'ep-1',
  connector_id: 'conn-1',
  name: 'My Endpoint',
  path: '/api/data',
  is_enabled: true,
  pagination_config: null,
  display_order: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
}

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function renderCard(endpoint = testEndpoint, onEdit = vi.fn()) {
  return render(
    React.createElement(EndpointCard, { endpoint, connectorId: 'conn-1', onEdit }),
    { wrapper: makeWrapper() }
  )
}

describe('DEL-06: EndpointCard 409 toast with canvas names', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset mockDeleteMutate to a fresh vi.fn() and update the hook mock
    mockDeleteMutate = vi.fn()
    vi.mocked(useDeleteEndpoint).mockReturnValue({
      mutate: mockDeleteMutate,
      isPending: false,
    } as ReturnType<typeof useDeleteEndpoint>)
  })

  it('shows destructive toast with canvas names when 409 ENDPOINT_IN_USE is returned', async () => {
    // Simulate the mutate call: capture the onError callback and invoke it
    mockDeleteMutate.mockImplementation((_params, callbacks) => {
      const axiosError = {
        response: {
          status: 409,
          data: {
            error: {
              code: 'ENDPOINT_IN_USE',
              message: 'Cannot delete',
              details: {
                canvas_names: ['Canvas Alpha', 'Canvas Beta'],
              },
            },
          },
        },
      }
      callbacks?.onError?.(axiosError)
    })

    renderCard()

    // Open the delete confirmation dialog
    const deleteBtn = screen.getByLabelText('Delete My Endpoint')
    await act(async () => {
      fireEvent.click(deleteBtn)
    })

    await waitFor(() => screen.getByText('Delete endpoint My Endpoint?'))

    // Confirm deletion
    const confirmBtn = screen.getByRole('button', { name: 'Delete' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Cannot delete endpoint',
          description: expect.stringContaining('Canvas Alpha'),
          variant: 'destructive',
        })
      )
    })

    // Both canvas names should appear in the description
    const callArgs = mockToast.mock.calls[0][0]
    expect(callArgs.description).toContain('Canvas Beta')
    expect(callArgs.description).toContain('Remove it from those canvases first')
  })

  it('shows generic error toast when non-409 error occurs', async () => {
    mockDeleteMutate.mockImplementation((_params, callbacks) => {
      callbacks?.onError?.({ response: { status: 500 } })
    })

    renderCard()

    const deleteBtn = screen.getByLabelText('Delete My Endpoint')
    await act(async () => {
      fireEvent.click(deleteBtn)
    })

    await waitFor(() => screen.getByText('Delete endpoint My Endpoint?'))

    const confirmBtn = screen.getByRole('button', { name: 'Delete' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to delete endpoint',
          variant: 'destructive',
        })
      )
    })
  })

  it('closes the dialog on successful deletion', async () => {
    mockDeleteMutate.mockImplementation((_params, callbacks) => {
      callbacks?.onSuccess?.()
    })

    renderCard()

    const deleteBtn = screen.getByLabelText('Delete My Endpoint')
    await act(async () => {
      fireEvent.click(deleteBtn)
    })

    await waitFor(() => screen.getByText('Delete endpoint My Endpoint?'))

    const confirmBtn = screen.getByRole('button', { name: 'Delete' })
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    await waitFor(() => {
      expect(screen.queryByText('Delete endpoint My Endpoint?')).toBeNull()
    })

    expect(mockToast).not.toHaveBeenCalled()
  })
})
