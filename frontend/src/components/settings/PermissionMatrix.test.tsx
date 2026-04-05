/**
 * Tests for PermissionMatrix — UI-02 gap coverage
 *
 * Verifies:
 * - Permission matrix renders 7 resources as rows
 * - CRUD columns (Create, Read, Update, Delete) render as headers
 * - Special column renders as header
 * - Checkboxes are disabled when disabled prop is true (system role)
 * - Checkboxes are enabled and reflect current permissions when disabled=false
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, vi, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// --- Mocks ---

vi.mock('@/hooks/queries/useRoles', () => ({
  useAddPermission: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRemovePermission: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: vi.fn(),
  useToast: vi.fn(() => ({ toast: vi.fn() })),
}))

import { PermissionMatrix } from './PermissionMatrix'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

const ALL_PERMISSIONS = [
  'connectors:create', 'connectors:read', 'connectors:update', 'connectors:delete', 'connectors:toggle_enabled',
  'canvases:create', 'canvases:read', 'canvases:update', 'canvases:delete',
  'schedules:create', 'schedules:read', 'schedules:update', 'schedules:delete',
  'runs:create', 'runs:read', 'runs:update', 'runs:delete', 'runs:trigger_sync',
  'settings:create', 'settings:read', 'settings:update', 'settings:delete',
  'users:create', 'users:read', 'users:update', 'users:delete',
  'roles:create', 'roles:read', 'roles:update', 'roles:delete',
]

describe('PermissionMatrix — resource rows (7 resources)', () => {
  it('renders Connectors resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Connectors')).toBeTruthy()
  })

  it('renders Canvases resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Canvases')).toBeTruthy()
  })

  it('renders Schedules resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Schedules')).toBeTruthy()
  })

  it('renders Runs resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Runs')).toBeTruthy()
  })

  it('renders Settings resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Settings')).toBeTruthy()
  })

  it('renders Users resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Users')).toBeTruthy()
  })

  it('renders Roles resource row', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    expect(screen.getByText('Roles')).toBeTruthy()
  })
})

describe('PermissionMatrix — CRUD + Special column headers', () => {
  function renderMatrix() {
    return render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
  }

  it('renders Create column header', () => {
    renderMatrix()
    expect(screen.getByText('create')).toBeTruthy()
  })

  it('renders Read column header', () => {
    renderMatrix()
    expect(screen.getByText('read')).toBeTruthy()
  })

  it('renders Update column header', () => {
    renderMatrix()
    expect(screen.getByText('update')).toBeTruthy()
  })

  it('renders Delete column header', () => {
    renderMatrix()
    expect(screen.getByText('delete')).toBeTruthy()
  })

  it('renders Special column header', () => {
    renderMatrix()
    expect(screen.getByText('Special')).toBeTruthy()
  })
})

describe('PermissionMatrix — disabled prop (system / Administrator role)', () => {
  it('renders all checkboxes as disabled when disabled=true', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={ALL_PERMISSIONS} disabled={true} />,
      { wrapper: makeWrapper() }
    )
    const checkboxes = screen.getAllByRole('checkbox')
    // All checkboxes should be disabled for system roles
    checkboxes.forEach((cb) => {
      expect(cb).toHaveProperty('disabled', true)
    })
  })

  it('renders checkboxes as enabled when disabled=false', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={[]} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    const checkboxes = screen.getAllByRole('checkbox')
    // At least one checkbox should not be disabled
    const enabledCheckboxes = checkboxes.filter((cb) => !(cb as HTMLInputElement).disabled)
    expect(enabledCheckboxes.length).toBeGreaterThan(0)
  })
})

describe('PermissionMatrix — checkbox reflects permissions', () => {
  // Radix UI Checkbox renders as a <button> with aria-checked and data-state attributes
  it('marks connectors:read checkbox as checked when permission is in permissions array', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={['connectors:read']} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    const checkbox = screen.getByRole('checkbox', { name: 'connectors:read' })
    expect(checkbox.getAttribute('data-state')).toBe('checked')
  })

  it('marks connectors:create checkbox as unchecked when permission is NOT in permissions array', () => {
    render(
      <PermissionMatrix roleId="r1" permissions={['connectors:read']} disabled={false} />,
      { wrapper: makeWrapper() }
    )
    const checkbox = screen.getByRole('checkbox', { name: 'connectors:create' })
    expect(checkbox.getAttribute('data-state')).toBe('unchecked')
  })
})
