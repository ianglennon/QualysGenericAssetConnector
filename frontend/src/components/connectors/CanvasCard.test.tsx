/**
 * Tests for CanvasCard component.
 *
 * MC-08: Inline rename via kebab menu — Enter saves, Escape cancels
 * MC-10: Enable/disable toggle calls useUpdateCanvas mutation
 * MC-11: Single-canvas sync via kebab menu calls useTriggerCanvasSync
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

const mockUpdateMutate = vi.fn()
const mockUpdateCanvas = { mutate: mockUpdateMutate, mutateAsync: vi.fn(), isPending: false }
vi.mock('@/hooks/queries/useCanvases', () => ({
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

import { CanvasCard } from './CanvasCard'

const enabledCanvas: CanvasListItem = {
  id: 'canvas-1',
  connector_id: 'conn-1',
  name: 'My Canvas',
  description: null,
  is_enabled: true,
  endpoint_count: 2,
  field_mapping_count: 3,
  last_run_status: null,
  last_run_at: null,
  created_at: '2026-03-01T00:00:00Z',
  updated_at: '2026-03-25T00:00:00Z',
}

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

function renderCard(canvas: CanvasListItem = enabledCanvas, onDelete = vi.fn(), onSync = vi.fn()) {
  return render(
    <CanvasCard canvas={canvas} connectorId="conn-1" onDelete={onDelete} onSync={onSync} />,
    { wrapper: makeWrapper() }
  )
}

// ---------------------------------------------------------------------------
// MC-08: Inline rename via kebab menu
// ---------------------------------------------------------------------------

describe('CanvasCard — MC-08: Inline rename', () => {
  beforeEach(() => {
    mockUpdateMutate.mockClear()
    mockToast.mockClear()
  })

  it('activates inline edit when Rename Canvas is selected from kebab menu', async () => {
    renderCard()

    const kebab = screen.getByLabelText('Canvas options')
    await act(async () => {
      fireEvent.pointerDown(kebab)
      fireEvent.click(kebab)
    })

    await waitFor(() => screen.getByText('Rename Canvas'))

    await act(async () => {
      fireEvent.click(screen.getByText('Rename Canvas'))
    })

    await waitFor(() => {
      // The input should be visible (InlineRename renders an Input with placeholder "Canvas name")
      expect(screen.getByPlaceholderText('Canvas name')).toBeDefined()
    })
  })

  it('saves new name when Enter is pressed during inline rename', async () => {
    renderCard()

    const kebab = screen.getByLabelText('Canvas options')
    await act(async () => {
      fireEvent.pointerDown(kebab)
      fireEvent.click(kebab)
    })

    await waitFor(() => screen.getByText('Rename Canvas'))
    await act(async () => {
      fireEvent.click(screen.getByText('Rename Canvas'))
    })

    await waitFor(() => screen.getByPlaceholderText('Canvas name'))

    const input = screen.getByPlaceholderText('Canvas name')
    fireEvent.change(input, { target: { value: 'Renamed Canvas' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => {
      expect(mockUpdateMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          connectorId: 'conn-1',
          canvasId: 'canvas-1',
          payload: { name: 'Renamed Canvas' },
        }),
        expect.anything()
      )
    })
  })

  it('cancels rename when Escape is pressed', async () => {
    renderCard()

    const kebab = screen.getByLabelText('Canvas options')
    await act(async () => {
      fireEvent.pointerDown(kebab)
      fireEvent.click(kebab)
    })

    await waitFor(() => screen.getByText('Rename Canvas'))
    await act(async () => {
      fireEvent.click(screen.getByText('Rename Canvas'))
    })

    await waitFor(() => screen.getByPlaceholderText('Canvas name'))

    const input = screen.getByPlaceholderText('Canvas name')
    fireEvent.keyDown(input, { key: 'Escape' })

    // After cancel, the input should be gone and the name heading should be back
    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Canvas name')).toBeNull()
      expect(screen.getByText('My Canvas')).toBeDefined()
    })
  })
})

// ---------------------------------------------------------------------------
// MC-10: Enable/disable toggle calls useUpdateCanvas mutation
// ---------------------------------------------------------------------------

describe('CanvasCard — MC-10: Enable/disable toggle', () => {
  beforeEach(() => {
    mockUpdateMutate.mockClear()
  })

  it('calls useUpdateCanvas with is_enabled:false when toggle is clicked on enabled canvas', async () => {
    renderCard(enabledCanvas)

    const toggle = screen.getByRole('switch', { name: /toggle My Canvas/i })
    await act(async () => {
      fireEvent.click(toggle.closest('div')!)
    })

    await waitFor(() => {
      expect(mockUpdateMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          connectorId: 'conn-1',
          canvasId: 'canvas-1',
          payload: { is_enabled: false },
        }),
        expect.anything()
      )
    })
  })

  it('calls useUpdateCanvas with is_enabled:true when toggle is clicked on disabled canvas', async () => {
    const disabledCanvas: CanvasListItem = { ...enabledCanvas, is_enabled: false }
    renderCard(disabledCanvas)

    const toggle = screen.getByRole('switch', { name: /toggle My Canvas/i })
    await act(async () => {
      fireEvent.click(toggle.closest('div')!)
    })

    await waitFor(() => {
      expect(mockUpdateMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          payload: { is_enabled: true },
        }),
        expect.anything()
      )
    })
  })

  it('renders disabled badge on disabled canvas', () => {
    const disabledCanvas: CanvasListItem = { ...enabledCanvas, is_enabled: false }
    renderCard(disabledCanvas)

    expect(screen.getByText('Disabled')).toBeDefined()
  })

  it('canvas card has reduced opacity when disabled', () => {
    const disabledCanvas: CanvasListItem = { ...enabledCanvas, is_enabled: false }
    const { container } = renderCard(disabledCanvas)

    // CanvasCard applies opacity-50 when disabled
    const card = container.querySelector('.opacity-50')
    expect(card).not.toBeNull()
  })
})

// ---------------------------------------------------------------------------
// MC-11: Single-canvas sync via kebab menu
// ---------------------------------------------------------------------------

describe('CanvasCard — MC-11: Single-canvas sync via kebab menu', () => {
  it('calls onSync prop when Sync this canvas is selected', async () => {
    const onSync = vi.fn()
    renderCard(enabledCanvas, vi.fn(), onSync)

    const kebab = screen.getByLabelText('Canvas options')
    await act(async () => {
      fireEvent.pointerDown(kebab)
      fireEvent.click(kebab)
    })

    await waitFor(() => screen.getByText('Sync this canvas'))

    await act(async () => {
      fireEvent.click(screen.getByText('Sync this canvas'))
    })

    await waitFor(() => {
      expect(onSync).toHaveBeenCalledWith(enabledCanvas)
    })
  })
})
