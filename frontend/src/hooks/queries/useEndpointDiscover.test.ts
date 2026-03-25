import { describe, it, vi, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api-client'
import { useCanvasDiscoverFields } from './useEndpointDiscover'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('FD-01: useCanvasDiscoverFields calls the canvas-aware discovery API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls the canvas-aware endpoint URL with connectorId, canvasId, and canvasEndpointRefId', async () => {
    const mockResponse = {
      data: {
        fields: [
          { path: 'id', type: 'string', sample_value: '123' },
          { path: '_parent.hostname', type: 'string', sample_value: 'host1' },
        ],
        record_count: 1,
      },
    }
    vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(() => useCanvasDiscoverFields(), {
      wrapper: makeWrapper(),
    })

    result.current.mutate({
      connectorId: 'conn-42',
      canvasId: 'canvas-99',
      canvasEndpointRefId: 'ref-7',
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(apiClient.get).toHaveBeenCalledWith(
      '/connectors/conn-42/canvases/canvas-99/endpoints/ref-7/fields/discover',
    )
  })

  it('returns the discovery response data on success', async () => {
    const mockFields = [
      { path: 'name', type: 'string', sample_value: 'test' },
    ]
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { fields: mockFields, record_count: 5 },
    })

    const { result } = renderHook(() => useCanvasDiscoverFields(), {
      wrapper: makeWrapper(),
    })

    result.current.mutate({
      connectorId: 'c1',
      canvasId: 'cv1',
      canvasEndpointRefId: 'r1',
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.fields).toEqual(mockFields)
    expect(result.current.data?.record_count).toBe(5)
  })
})
