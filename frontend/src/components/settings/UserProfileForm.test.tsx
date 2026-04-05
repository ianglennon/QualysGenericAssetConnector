/**
 * Tests for UserProfileForm — UI-05 gap coverage (must_change_password banner)
 *
 * Verifies:
 * - Banner renders when mustChangePassword is true
 * - Banner is absent when mustChangePassword is false
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, vi, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// --- Mocks ---

const mockChangePassword = { mutate: vi.fn(), isPending: false }
const mockUpdatePreferences = { mutate: vi.fn(), isPending: false }

vi.mock('@/hooks/queries/useUser', () => ({
  useChangePassword: vi.fn(() => mockChangePassword),
  useUpdatePreferences: vi.fn(() => mockUpdatePreferences),
}))

vi.mock('@/lib/api-client', () => ({
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getAccessToken: vi.fn(() => null),
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
  useToast: vi.fn(() => ({ toast: vi.fn() })),
}))

// mustChangePassword is controlled per test via this mock
let mockMustChangePassword = false

vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: '1',
      email: 'user@example.com',
      is_active: true,
      must_change_password: mockMustChangePassword,
      role: { id: 'r1', name: 'Administrator', is_system: true, permissions: [] },
    },
    hasPermission: () => false,
    mustChangePassword: mockMustChangePassword,
  })),
}))

import { UserProfileForm } from './UserProfileForm'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('UserProfileForm — must_change_password banner', () => {
  it('renders the forced password change banner when mustChangePassword is true', () => {
    mockMustChangePassword = true
    render(<UserProfileForm />, { wrapper: makeWrapper() })
    expect(
      screen.getByText(/you must change your password before continuing/i)
    ).toBeTruthy()
  })

  it('does not render the forced password change banner when mustChangePassword is false', () => {
    mockMustChangePassword = false
    render(<UserProfileForm />, { wrapper: makeWrapper() })
    expect(
      screen.queryByText(/you must change your password before continuing/i)
    ).toBeNull()
  })
})
