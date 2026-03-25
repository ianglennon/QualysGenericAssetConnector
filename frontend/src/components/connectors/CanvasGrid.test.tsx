/**
 * Tests for CanvasGrid and canvas CRUD dialogs.
 *
 * MC-06: Canvas card grid renders cards with name, endpoint count, badges
 * MC-07: Create canvas dialog opens on button click and submits
 * MC-09: Delete confirmation dialog shows endpoint/mapping impact summary
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { CanvasListItem } from '@/types/canvas'

// --- Mocks ---

const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

const mockCanvases: CanvasListItem[] = [
  {
    id: 'canvas-1',
    connector_id: 'conn-1',
    name: 'Primary Canvas',
    description: 'Main data flow',
    is_enabled: true,
    endpoint_count: 3,
    field_mapping_count: 5,
    last_run_status: 'success',
    last_run_at: '2026-03-25T10:00:00Z',
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-25T10:00:00Z',
  },
  {
    id: 'canvas-2',
    connector_id: 'conn-1',
    name: 'Secondary Canvas',
    description: null,
    is_enabled: false,
    endpoint_count: 1,
    field_mapping_count: 2,
    last_run_status: 'failed',
    last_run_at: '2026-03-24T08:00:00Z',
    created_at: '2026-03-02T00:00:00Z',
    updated_at: '2026-03-24T08:00:00Z',
  },
]

const mockUseCanvases = vi.fn()
const mockCreateCanvas = { mutateAsync: vi.fn(), isPending: false }
const mockDeleteCanvas = { mutateAsync: vi.fn(), isPending: false }
const mockTriggerSync = { mutateAsync: vi.fn(), isPending: false }
const mockUpdateCanvas = { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }

vi.mock('@/hooks/queries/useCanvases', () => ({
  useCanvases: (...args: unknown[]) => mockUseCanvases(...args),
  useCreateCanvas: vi.fn(() => mockCreateCanvas),
  useDeleteCanvas: vi.fn(() => mockDeleteCanvas),
  useTriggerCanvasSync: vi.fn(() => mockTriggerSync),
  useUpdateCanvas: vi.fn(() => mockUpdateCanvas),
}))

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

vi.mock('@/routes/constants', () => ({
  ROUTES: {
    connectorCanvas: (connId: string, canvasId: string) => `/connectors/${connId}/canvases/${canvasId}`,
  },
}))

import { CanvasGrid } from './CanvasGrid'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// ---------------------------------------------------------------------------
// MC-06: Canvas card grid renders cards with name, endpoint count, badges
// ---------------------------------------------------------------------------

describe('CanvasGrid — MC-06: Card grid display', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    mockToast.mockClear()
    mockUseCanvases.mockReturnValue({ data: mockCanvases, isLoading: false, isError: false })
  })

  it('renders canvas cards with canvas names', () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText('Primary Canvas')).toBeDefined()
    expect(screen.getByText('Secondary Canvas')).toBeDefined()
  })

  it('displays endpoint count on each canvas card', () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText('3 endpoints')).toBeDefined()
    expect(screen.getByText('1 endpoint')).toBeDefined()
  })

  it('displays enabled/disabled badge on each card', () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText('Enabled')).toBeDefined()
    expect(screen.getByText('Disabled')).toBeDefined()
  })

  it('shows last run status badge', () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText('Success')).toBeDefined()
    expect(screen.getByText('Failed')).toBeDefined()
  })

  it('shows loading skeletons when data is loading', () => {
    mockUseCanvases.mockReturnValue({ data: undefined, isLoading: true, isError: false })
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText('Canvases')).toBeDefined()
    // Skeletons rendered, no canvas names
    expect(screen.queryByText('Primary Canvas')).toBeNull()
  })

  it('shows error message when data loading fails', () => {
    mockUseCanvases.mockReturnValue({ data: undefined, isLoading: false, isError: true })
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText(/failed to load canvases/i)).toBeDefined()
  })

  it('shows empty state when no canvases exist', () => {
    mockUseCanvases.mockReturnValue({ data: [], isLoading: false, isError: false })
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    expect(screen.getByText('No canvases yet')).toBeDefined()
  })

  it('navigates to canvas editor when card body is clicked', async () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    const card = screen.getByText('Primary Canvas').closest('[class*="cursor-pointer"]')
    if (card) {
      fireEvent.click(card)
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/connectors/conn-1/canvases/canvas-1')
      })
    }
  })
})

// ---------------------------------------------------------------------------
// MC-07: Create canvas dialog opens and submits
// ---------------------------------------------------------------------------

describe('CanvasGrid — MC-07: Create canvas dialog', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
    mockToast.mockClear()
    mockUseCanvases.mockReturnValue({ data: mockCanvases, isLoading: false, isError: false })
    mockCreateCanvas.mutateAsync.mockResolvedValue({ id: 'new-canvas-id' })
  })

  it('shows New Canvas button', () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })
    expect(screen.getByRole('button', { name: /new canvas/i })).toBeDefined()
  })

  it('opens create canvas dialog when New Canvas button is clicked', async () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    const btn = screen.getByRole('button', { name: /new canvas/i })
    await act(async () => {
      fireEvent.click(btn)
    })

    await waitFor(() => {
      // 'New Canvas' appears in the dialog title
      const labels = screen.getAllByText('New Canvas')
      expect(labels.length).toBeGreaterThan(0)
      expect(screen.getByLabelText('Name')).toBeDefined()
    })
  })

  it('submits create form with name and navigates to new canvas', async () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    fireEvent.click(screen.getByRole('button', { name: /new canvas/i }))

    await waitFor(() => screen.getByLabelText('Name'))

    const nameInput = screen.getByLabelText('Name')
    fireEvent.change(nameInput, { target: { value: 'New Test Canvas' } })

    const submitBtn = screen.getByRole('button', { name: /create canvas/i })
    await act(async () => {
      fireEvent.click(submitBtn)
    })

    await waitFor(() => {
      expect(mockCreateCanvas.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ connectorId: 'conn-1', name: 'New Test Canvas' })
      )
    })
  })
})

// ---------------------------------------------------------------------------
// MC-09: Delete confirmation dialog shows impact summary
// ---------------------------------------------------------------------------

describe('CanvasGrid — MC-09: Delete confirmation with impact summary', () => {
  beforeEach(() => {
    mockUseCanvases.mockReturnValue({ data: mockCanvases, isLoading: false, isError: false })
    mockDeleteCanvas.mutateAsync.mockResolvedValue(undefined)
    mockToast.mockClear()
  })

  it('opens delete dialog with endpoint and mapping counts when Delete Canvas is clicked', async () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    // Open kebab menu for Primary Canvas using pointer events (Radix UI requirement)
    const kebabButtons = screen.getAllByLabelText('Canvas options')
    await act(async () => {
      fireEvent.pointerDown(kebabButtons[0])
      fireEvent.click(kebabButtons[0])
    })

    await waitFor(() => screen.getByText('Delete Canvas'))

    const deleteItem = screen.getByText('Delete Canvas')
    await act(async () => {
      fireEvent.click(deleteItem)
    })

    await waitFor(() => {
      // DeleteCanvasDialog shows canvas name in a <strong> tag
      const matches = screen.getAllByText('Primary Canvas')
      const inStrong = matches.some((el) => el.tagName === 'STRONG')
      expect(inStrong).toBe(true)
      // The dialog description contains "3 endpoint references" (distinct from card "3 endpoints")
      expect(screen.getByText(/3 endpoint references/i)).toBeDefined()
      // The dialog description contains "5 field mappings"
      expect(screen.getByText(/5 field mappings/i)).toBeDefined()
    })
  })

  it('calls deleteCanvas mutation when Delete Canvas button is confirmed', async () => {
    render(<CanvasGrid connectorId="conn-1" />, { wrapper: makeWrapper() })

    const kebabButtons = screen.getAllByLabelText('Canvas options')
    await act(async () => {
      fireEvent.pointerDown(kebabButtons[0])
      fireEvent.click(kebabButtons[0])
    })

    await waitFor(() => screen.getByText('Delete Canvas'))
    await act(async () => {
      fireEvent.click(screen.getByText('Delete Canvas'))
    })

    // Confirm deletion in dialog
    await waitFor(() => screen.getByRole('button', { name: /delete canvas/i }))
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /delete canvas/i }))
    })

    await waitFor(() => {
      expect(mockDeleteCanvas.mutateAsync).toHaveBeenCalledWith({
        connectorId: 'conn-1',
        canvasId: 'canvas-1',
      })
    })
  })
})
