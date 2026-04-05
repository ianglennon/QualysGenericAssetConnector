import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConnectorListPage } from './ConnectorListPage'

// --- Module-level mocks ---

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

vi.mock('@/hooks/queries/useConnectors', () => ({
  useConnectors: vi.fn(() => ({
    data: [
      {
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
    ],
    isLoading: false,
  })),
  useCreateConnector: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useUpdateConnector: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteConnector: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

const mockMutateAsync = vi.fn().mockResolvedValue({ id: 'run-1', status: 'running' })

vi.mock('@/hooks/queries/useRuns', () => ({
  useTriggerRun: vi.fn(() => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  })),
}))

const adminPermissions = ['connectors:create', 'connectors:read', 'connectors:update', 'connectors:delete']

vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: '1', email: 'admin@example.com', is_active: true, must_change_password: false,
      role: { id: 'r1', name: 'Administrator', is_system: true, permissions: adminPermissions },
    },
    hasPermission: (p: string) => adminPermissions.includes(p),
  })),
}))

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

// --- QueryClient wrapper ---

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// --- Tests ---

describe('ConnectorListPage', () => {
  beforeEach(() => {
    mockMutateAsync.mockClear()
    mockToast.mockClear()
  })

  it('renders Play button on ConnectorCard', () => {
    render(<ConnectorListPage />, { wrapper: makeWrapper() })
    const triggerBtn = screen.getByTitle('Trigger Sync')
    expect(triggerBtn).toBeTruthy()
  })
})
