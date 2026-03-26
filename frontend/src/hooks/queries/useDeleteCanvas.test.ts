/**
 * DEL-05: useDeleteCanvas optimistic UI — canvas card disappears immediately
 * from the cache on delete and rolls back if the API call fails.
 */
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { CanvasListItem } from '@/types/canvas'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    delete: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api-client'
import { useDeleteCanvas } from './useCanvases'

const canvas1: CanvasListItem = {
  id: 'canvas-1',
  connector_id: 'conn-1',
  name: 'Canvas One',
  description: null,
  is_enabled: true,
  endpoint_count: 1,
  field_mapping_count: 2,
  last_run_status: null,
  last_run_at: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
}

const canvas2: CanvasListItem = {
  ...canvas1,
  id: 'canvas-2',
  name: 'Canvas Two',
}

const QUERY_KEY = ['canvases', 'conn-1']

function makeWrapper(qc: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('DEL-05: useDeleteCanvas optimistic delete with rollback', () => {
  let qc: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    // Pre-populate cache with two canvases
    qc.setQueryData<CanvasListItem[]>(QUERY_KEY, [canvas1, canvas2])
  })

  it('removes the canvas from the cache immediately (before API resolves)', async () => {
    // Delay API resolution so we can inspect cache mid-flight
    let resolveDelete!: () => void
    vi.mocked(apiClient.delete).mockReturnValueOnce(
      new Promise<void>((res) => {
        resolveDelete = res
      })
    )

    const { result } = renderHook(() => useDeleteCanvas(), {
      wrapper: makeWrapper(qc),
    })

    act(() => {
      result.current.mutate({ connectorId: 'conn-1', canvasId: 'canvas-1' })
    })

    // onMutate fires synchronously — cache should already be filtered
    await waitFor(() => {
      const cached = qc.getQueryData<CanvasListItem[]>(QUERY_KEY)
      expect(cached?.find((c) => c.id === 'canvas-1')).toBeUndefined()
    })

    // canvas-2 is still there
    const cached = qc.getQueryData<CanvasListItem[]>(QUERY_KEY)
    expect(cached?.find((c) => c.id === 'canvas-2')).toBeDefined()

    // Let the API resolve so the mutation completes cleanly
    resolveDelete()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })

  it('restores the canvas list when the API call fails (rollback)', async () => {
    vi.mocked(apiClient.delete).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useDeleteCanvas(), {
      wrapper: makeWrapper(qc),
    })

    act(() => {
      result.current.mutate({ connectorId: 'conn-1', canvasId: 'canvas-1' })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))

    // onError rollback should have restored previous state
    const cached = qc.getQueryData<CanvasListItem[]>(QUERY_KEY)
    expect(cached?.find((c) => c.id === 'canvas-1')).toBeDefined()
    expect(cached?.length).toBe(2)
  })

  it('calls the correct API URL on delete', async () => {
    vi.mocked(apiClient.delete).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() => useDeleteCanvas(), {
      wrapper: makeWrapper(qc),
    })

    act(() => {
      result.current.mutate({ connectorId: 'conn-1', canvasId: 'canvas-1' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.delete).toHaveBeenCalledWith('/connectors/conn-1/canvases/canvas-1')
  })
})
