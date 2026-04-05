/**
 * Tests for UsersPage — UI-01 gap coverage
 *
 * Verifies:
 * - User table renders with columns (Email, Role, Status, Created, Actions)
 * - Add User button gated by users:create permission
 * - Edit button visible for users with users:update permission
 * - Deactivate button hidden on current user's own row (self-deactivation guard)
 * - Deactivate button visible on other users' rows
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// --- Mocks ---

const CURRENT_USER_ID = 'user-current'
const OTHER_USER_ID = 'user-other'

const mockUsers = [
  {
    id: CURRENT_USER_ID,
    email: 'current@example.com',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    role: { id: 'r1', name: 'Administrator' },
  },
  {
    id: OTHER_USER_ID,
    email: 'other@example.com',
    is_active: false,
    created_at: '2026-02-15T00:00:00Z',
    role: { id: 'r2', name: 'Operator' },
  },
]

vi.mock('@/hooks/queries/useUsers', () => ({
  useUsers: vi.fn(() => ({
    data: mockUsers,
    isLoading: false,
  })),
  useCreateUser: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useUpdateUser: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeactivateUser: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

vi.mock('@/components/settings/UserCreateDialog', () => ({
  UserCreateDialog: () => null,
}))

vi.mock('@/components/settings/UserEditDialog', () => ({
  UserEditDialog: () => null,
}))

vi.mock('@/components/settings/UserDeactivateDialog', () => ({
  UserDeactivateDialog: () => null,
}))

// Default: full admin permissions
let mockPermissions = ['users:read', 'users:create', 'users:update', 'users:delete']
let mockCurrentUserId = CURRENT_USER_ID

const mockUseAuth = vi.fn(() => ({
  user: {
    id: mockCurrentUserId,
    email: 'current@example.com',
    is_active: true,
    must_change_password: false,
    role: { id: 'r1', name: 'Administrator', is_system: true, permissions: mockPermissions },
  },
  hasPermission: (p: string) => mockPermissions.includes(p),
  mustChangePassword: false,
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

import { UsersPage } from './UsersPage'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

function renderPage() {
  return render(<UsersPage />, { wrapper: makeWrapper() })
}

describe('UsersPage — table columns render', () => {
  beforeEach(() => {
    mockPermissions = ['users:read', 'users:create', 'users:update', 'users:delete']
    mockCurrentUserId = CURRENT_USER_ID
  })

  it('renders the Email column header', () => {
    renderPage()
    expect(screen.getByText('Email')).toBeTruthy()
  })

  it('renders the Role column header', () => {
    renderPage()
    expect(screen.getByText('Role')).toBeTruthy()
  })

  it('renders the Status column header', () => {
    renderPage()
    expect(screen.getByText('Status')).toBeTruthy()
  })

  it('renders the Created column header', () => {
    renderPage()
    expect(screen.getByText('Created')).toBeTruthy()
  })

  it('renders the Actions column header', () => {
    renderPage()
    expect(screen.getByText('Actions')).toBeTruthy()
  })

  it('renders user email in table rows', () => {
    renderPage()
    expect(screen.getByText('current@example.com')).toBeTruthy()
    expect(screen.getByText('other@example.com')).toBeTruthy()
  })

  it('renders role name in table rows', () => {
    renderPage()
    expect(screen.getByText('Administrator')).toBeTruthy()
    expect(screen.getByText('Operator')).toBeTruthy()
  })

  it('renders Active badge for active user', () => {
    renderPage()
    expect(screen.getByText('Active')).toBeTruthy()
  })

  it('renders Inactive badge for inactive user', () => {
    renderPage()
    expect(screen.getByText('Inactive')).toBeTruthy()
  })
})

describe('UsersPage — Add User button permission gating', () => {
  beforeEach(() => {
    mockCurrentUserId = CURRENT_USER_ID
  })

  it('shows Add User button when user has users:create permission', () => {
    mockPermissions = ['users:read', 'users:create', 'users:update']
    renderPage()
    expect(screen.getByRole('button', { name: /add user/i })).toBeTruthy()
  })

  it('hides Add User button when user lacks users:create permission', () => {
    mockPermissions = ['users:read', 'users:update']
    renderPage()
    expect(screen.queryByRole('button', { name: /add user/i })).toBeNull()
  })
})

describe('UsersPage — Edit button visibility', () => {
  beforeEach(() => {
    mockCurrentUserId = CURRENT_USER_ID
  })

  it('shows Edit buttons when user has users:update permission', () => {
    mockPermissions = ['users:read', 'users:update']
    renderPage()
    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    expect(editButtons.length).toBeGreaterThan(0)
  })

  it('hides Edit buttons when user lacks users:update permission', () => {
    mockPermissions = ['users:read']
    renderPage()
    expect(screen.queryByRole('button', { name: /edit/i })).toBeNull()
  })
})

describe('UsersPage — Self-deactivation guard (D-05)', () => {
  beforeEach(() => {
    mockPermissions = ['users:read', 'users:update']
  })

  it('hides Deactivate button on the current user own row', () => {
    mockCurrentUserId = CURRENT_USER_ID
    renderPage()
    // current@example.com is current user — should have no deactivate button
    expect(
      screen.queryByRole('button', { name: /deactivate current@example.com/i })
    ).toBeNull()
  })

  it('shows Deactivate button on other users rows', () => {
    mockCurrentUserId = CURRENT_USER_ID
    renderPage()
    // other@example.com is NOT current user — should have a deactivate button
    expect(
      screen.getByRole('button', { name: /deactivate other@example.com/i })
    ).toBeTruthy()
  })
})
