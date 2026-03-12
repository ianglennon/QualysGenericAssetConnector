import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConnectorDetailPage } from './ConnectorDetailPage'

// --- Module-level mocks ---

vi.mock('react-router-dom', () => ({
  useParams: vi.fn(() => ({ id: 'conn-1' })),
}))

vi.mock('@/hooks/queries/useConnectors', () => ({
  useConnector: vi.fn(() => ({
    data: {
      id: 'conn-1',
      name: 'Test Connector',
      base_url: 'https://api.example.com',
      auth_method: 'bearer_token',
      has_token: true,
      has_username: false,
      has_api_key: false,
      has_valid_endpoints: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    isLoading: false,
  })),
}))

const mockMutateAsync = vi.fn().mockResolvedValue({ id: 'run-1', status: 'running' })

vi.mock('@/hooks/queries/useRuns', () => ({
  useTriggerRun: vi.fn(() => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  })),
}))

vi.mock('@/hooks/queries/useEndpoints', () => ({
  useEndpoints: vi.fn(() => ({
    data: [],
    isLoading: false,
  })),
}))

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

// Mock EndpointList to avoid deep dependency tree
vi.mock('@/components/connectors/EndpointList', () => ({
  EndpointList: () => <div data-testid="endpoint-list" />,
}))

// --- QueryClient wrapper ---

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// --- Tests ---

describe('ConnectorDetailPage', () => {
  beforeEach(() => {
    mockMutateAsync.mockClear()
    mockToast.mockClear()
  })

  it('calls useTriggerRun when Trigger Sync clicked', async () => {
    render(<ConnectorDetailPage />, { wrapper: makeWrapper() })
    const btn = screen.getByRole('button', { name: /trigger sync/i })
    fireEvent.click(btn)
    await waitFor(() =>
      expect(mockMutateAsync).toHaveBeenCalledWith('conn-1')
    )
  })

  it('disables Trigger Sync when has_valid_endpoints is false', async () => {
    const { useConnector } = await import('@/hooks/queries/useConnectors')
    vi.mocked(useConnector).mockReturnValueOnce({
      data: {
        id: 'conn-1',
        name: 'Test Connector',
        base_url: 'https://api.example.com',
        auth_method: 'bearer_token',
        has_token: true,
        has_username: false,
        has_api_key: false,
        has_valid_endpoints: false,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
      isLoading: false,
    } as any)
    render(<ConnectorDetailPage />, { wrapper: makeWrapper() })
    const btn = screen.getByRole('button', { name: /trigger sync/i })
    expect(btn).toBeDisabled()
  })

  it('shows toast on successful trigger', async () => {
    render(<ConnectorDetailPage />, { wrapper: makeWrapper() })
    const btn = screen.getByRole('button', { name: /trigger sync/i })
    fireEvent.click(btn)
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Sync triggered' })
      )
    )
  })
})
