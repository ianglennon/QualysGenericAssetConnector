import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, vi, expect } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ROUTES } from '@/routes/constants'

// --- Module-level mocks ---
// Default mock: admin user
const mockUseAuth = vi.fn(() => ({
  user: { role: 'admin', email: 'admin@example.com' },
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

// Import Sidebar after mocks are in place
import { Sidebar } from './Sidebar'

// ---  ROUTES constant tests ---

describe('ROUTES constants', () => {
  it('ROUTES.RUNS equals "/runs"', () => {
    expect(ROUTES.RUNS).toBe('/runs')
  })

  it('ROUTES.DASHBOARD equals "/dashboard"', () => {
    expect(ROUTES.DASHBOARD).toBe('/dashboard')
  })

  it('ROUTES.LOGIN equals "/login"', () => {
    expect(ROUTES.LOGIN).toBe('/login')
  })

  it('ROUTES.CONNECTORS equals "/connectors"', () => {
    expect(ROUTES.CONNECTORS).toBe('/connectors')
  })

  it('ROUTES.SETTINGS equals "/settings"', () => {
    expect(ROUTES.SETTINGS).toBe('/settings')
  })

  it('ROUTES.connectorDetail("123") equals "/connectors/123"', () => {
    expect(ROUTES.connectorDetail('123')).toBe('/connectors/123')
  })

  it('ROUTES.runDetail("456") equals "/runs/456"', () => {
    expect(ROUTES.runDetail('456')).toBe('/runs/456')
  })

  it('ROUTES.connectorMappings("1", "2") equals "/connectors/1/endpoints/2/mappings"', () => {
    expect(ROUTES.connectorMappings('1', '2')).toBe('/connectors/1/endpoints/2/mappings')
  })
})

// --- Sidebar component tests ---

function renderSidebar(initialPath = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Sidebar />
    </MemoryRouter>
  )
}

describe('Sidebar navigation links', () => {
  it('renders "Run History" link with href pointing to ROUTES.RUNS ("/runs")', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'admin', email: 'admin@example.com' } })
    renderSidebar()
    const runHistoryLink = screen.getByRole('link', { name: /run history/i })
    expect(runHistoryLink).toHaveAttribute('href', ROUTES.RUNS)
  })

  it('renders "Dashboard" link with href pointing to ROUTES.DASHBOARD ("/dashboard")', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'admin', email: 'admin@example.com' } })
    renderSidebar()
    const dashboardLink = screen.getByRole('link', { name: /dashboard/i })
    expect(dashboardLink).toHaveAttribute('href', ROUTES.DASHBOARD)
  })

  it('renders "Connectors" link with href pointing to ROUTES.CONNECTORS ("/connectors")', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'admin', email: 'admin@example.com' } })
    renderSidebar()
    const connectorsLink = screen.getByRole('link', { name: /connectors/i })
    expect(connectorsLink).toHaveAttribute('href', ROUTES.CONNECTORS)
  })

  it('admin user sees Settings link', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'admin', email: 'admin@example.com' } })
    renderSidebar()
    expect(screen.getByRole('link', { name: /^settings$/i })).toBeTruthy()
  })
})

describe('Sidebar role filtering', () => {
  it('operator user does NOT see Settings link', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'operator', email: 'op@example.com' } })
    renderSidebar()
    const settingsLink = screen.queryByRole('link', { name: /^settings$/i })
    expect(settingsLink).toBeNull()
  })
})
