/**
 * Tests for ScheduleBuilder component.
 *
 * UI-01: Admin can configure interval type and value
 * UI-02: Frontend validation enforces min/max constraints per interval type
 * UI-04: Enable/disable toggle pauses or resumes schedule without confirmation
 */
import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Connector } from '@/types/api'

// --- Mocks ---

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

const mockSaveMutateAsync = vi.fn()
const mockPauseMutateAsync = vi.fn()
const mockResumeMutateAsync = vi.fn()

vi.mock('@/hooks/queries/useSchedule', () => ({
  useSaveSchedule: vi.fn(() => ({
    mutateAsync: mockSaveMutateAsync,
    isPending: false,
  })),
  usePauseSchedule: vi.fn(() => ({
    mutateAsync: mockPauseMutateAsync,
    isPending: false,
  })),
  useResumeSchedule: vi.fn(() => ({
    mutateAsync: mockResumeMutateAsync,
    isPending: false,
  })),
}))

// Default: user with schedules:update permission
let mockHasPermission = true
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: '1', email: 'admin@example.com', is_active: true, must_change_password: false,
      role: { id: 'r1', name: 'Administrator', is_system: true, permissions: ['schedules:update'] },
    },
    hasPermission: (p: string) => mockHasPermission && p === 'schedules:update',
  })),
}))

import { ScheduleBuilder } from './ScheduleBuilder'

function makeConnector(overrides: Partial<Connector> = {}): Connector {
  return {
    id: 'conn-1',
    name: 'Test Connector',
    base_url: 'https://example.com',
    auth_method: 'bearer_token',
    has_token: true,
    has_username: false,
    has_password: false,
    has_api_key: false,
    has_valid_endpoints: true,
    verify_ssl: true,
    fault_diagnosis: false,
    interval_type: null,
    interval_value: null,
    schedule_enabled: false,
    next_run_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

function renderBuilder(connector: Connector = makeConnector()) {
  return render(
    <ScheduleBuilder connectorId="conn-1" connector={connector} />,
    { wrapper: makeWrapper() }
  )
}

// ---------------------------------------------------------------------------
// UI-01: Interval picker configuration
// ---------------------------------------------------------------------------

describe('ScheduleBuilder — UI-01: Interval picker configuration', () => {
  beforeEach(() => {
    mockHasPermission = true
    mockSaveMutateAsync.mockClear()
    mockToast.mockClear()
  })

  it('renders the Schedule heading for admin users', () => {
    renderBuilder()
    expect(screen.getByText('Schedule')).toBeDefined()
  })

  it('renders interval value input for admin users', () => {
    renderBuilder()
    expect(screen.getByPlaceholderText('Value')).toBeDefined()
  })

  it('renders the "Run every" label above the picker', () => {
    renderBuilder()
    expect(screen.getByText('Run every')).toBeDefined()
  })

  it('renders Save Schedule button', () => {
    renderBuilder()
    expect(screen.getByRole('button', { name: /Save Schedule/i })).toBeDefined()
  })

  it('Save Schedule button is disabled when no value is entered', () => {
    renderBuilder(makeConnector({ interval_type: null, interval_value: null }))
    const btn = screen.getByRole('button', { name: /Save Schedule/i })
    expect(btn).toHaveProperty('disabled', true)
  })

  it('calls useSaveSchedule mutateAsync with interval_type and interval_value on save', async () => {
    mockSaveMutateAsync.mockResolvedValue({})
    renderBuilder(makeConnector({ interval_type: 'hours', interval_value: 6, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    // Change value so it differs from server state (interval_value=6 -> 8)
    fireEvent.change(input, { target: { value: '8' } })

    const btn = screen.getByRole('button', { name: /Save Schedule/i })
    await act(async () => {
      fireEvent.click(btn)
    })

    await waitFor(() => {
      expect(mockSaveMutateAsync).toHaveBeenCalledWith({
        interval_type: 'hours',
        interval_value: 8,
      })
    })
  })

  it('does not render schedule panel for users without schedules:update permission', () => {
    mockHasPermission = false
    const { container } = renderBuilder()
    // ScheduleBuilder returns null when permission is missing
    expect(container.firstChild).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// UI-02: Frontend validation (min/max constraints)
// ---------------------------------------------------------------------------

describe('ScheduleBuilder — UI-02: Frontend validation', () => {
  beforeEach(() => {
    mockHasPermission = true
    mockSaveMutateAsync.mockClear()
    mockToast.mockClear()
  })

  it('shows validation error when hours value is 0 (below min of 1)', async () => {
    renderBuilder(makeConnector({ interval_type: 'hours', interval_value: 6, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    fireEvent.change(input, { target: { value: '0' } })

    await waitFor(() => {
      expect(screen.getByText(/Hours must be between 1 and 168/i)).toBeDefined()
    })
  })

  it('shows validation error when hours value exceeds max of 168', async () => {
    renderBuilder(makeConnector({ interval_type: 'hours', interval_value: 6, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    fireEvent.change(input, { target: { value: '200' } })

    await waitFor(() => {
      expect(screen.getByText(/Hours must be between 1 and 168/i)).toBeDefined()
    })
  })

  it('shows validation error when minutes value is below min of 5', async () => {
    renderBuilder(makeConnector({ interval_type: 'minutes', interval_value: 30, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    fireEvent.change(input, { target: { value: '2' } })

    await waitFor(() => {
      expect(screen.getByText(/Minutes must be between 5 and 1,440/i)).toBeDefined()
    })
  })

  it('Save Schedule button is disabled when there is a validation error', async () => {
    renderBuilder(makeConnector({ interval_type: 'hours', interval_value: 6, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    fireEvent.change(input, { target: { value: '0' } })

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /Save Schedule/i })
      expect(btn).toHaveProperty('disabled', true)
    })
  })

  it('clears validation error when a valid value is entered', async () => {
    renderBuilder(makeConnector({ interval_type: 'hours', interval_value: 6, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')

    // First enter invalid value
    fireEvent.change(input, { target: { value: '0' } })
    await waitFor(() => {
      expect(screen.getByText(/Hours must be between/i)).toBeDefined()
    })

    // Then enter valid value
    fireEvent.change(input, { target: { value: '12' } })
    await waitFor(() => {
      expect(screen.queryByText(/Hours must be between/i)).toBeNull()
    })
  })

  it('shows validation error for days value above max of 365', async () => {
    renderBuilder(makeConnector({ interval_type: 'days', interval_value: 7, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    fireEvent.change(input, { target: { value: '400' } })

    await waitFor(() => {
      expect(screen.getByText(/Days must be between 1 and 365/i)).toBeDefined()
    })
  })

  it('shows validation error for weeks value above max of 52', async () => {
    renderBuilder(makeConnector({ interval_type: 'weeks', interval_value: 2, schedule_enabled: true }))

    const input = screen.getByPlaceholderText('Value')
    fireEvent.change(input, { target: { value: '60' } })

    await waitFor(() => {
      expect(screen.getByText(/Weeks must be between 1 and 52/i)).toBeDefined()
    })
  })
})

// ---------------------------------------------------------------------------
// UI-04: Enable/disable toggle pauses or resumes schedule
// ---------------------------------------------------------------------------

describe('ScheduleBuilder — UI-04: Enable/disable toggle', () => {
  beforeEach(() => {
    mockHasPermission = true
    mockPauseMutateAsync.mockClear()
    mockResumeMutateAsync.mockClear()
    mockToast.mockClear()
  })

  it('renders Schedule Enabled label next to the toggle', () => {
    renderBuilder(makeConnector({ interval_type: 'hours', interval_value: 6, schedule_enabled: true }))
    expect(screen.getByText('Schedule Enabled')).toBeDefined()
  })

  it('calls pauseSchedule when toggle is clicked on an enabled schedule', async () => {
    mockPauseMutateAsync.mockResolvedValue({})
    renderBuilder(makeConnector({
      interval_type: 'hours',
      interval_value: 6,
      schedule_enabled: true,
    }))

    const toggle = screen.getByRole('switch', { name: /Enable or disable automatic schedule/i })
    await act(async () => {
      fireEvent.click(toggle)
    })

    await waitFor(() => {
      expect(mockPauseMutateAsync).toHaveBeenCalled()
    })
  })

  it('calls resumeSchedule when toggle is clicked on a paused schedule', async () => {
    mockResumeMutateAsync.mockResolvedValue({})
    renderBuilder(makeConnector({
      interval_type: 'hours',
      interval_value: 6,
      schedule_enabled: false,
    }))

    const toggle = screen.getByRole('switch', { name: /Enable or disable automatic schedule/i })
    await act(async () => {
      fireEvent.click(toggle)
    })

    await waitFor(() => {
      expect(mockResumeMutateAsync).toHaveBeenCalled()
    })
  })

  it('toggle is disabled when no schedule is configured (interval_type is null)', () => {
    renderBuilder(makeConnector({ interval_type: null, interval_value: null, schedule_enabled: false }))
    const toggle = screen.getByRole('switch', { name: /Enable or disable automatic schedule/i })
    expect(toggle).toHaveProperty('disabled', true)
  })

  it('inputs are dimmed (opacity-50) when schedule is paused', () => {
    const { container } = renderBuilder(makeConnector({
      interval_type: 'hours',
      interval_value: 6,
      schedule_enabled: false,
    }))
    const dimmedEl = container.querySelector('.opacity-50')
    expect(dimmedEl).not.toBeNull()
  })

  it('inputs are NOT dimmed when schedule is active', () => {
    const { container } = renderBuilder(makeConnector({
      interval_type: 'hours',
      interval_value: 6,
      schedule_enabled: true,
    }))
    // The interval picker wrapper has opacity-50 applied only in paused state.
    // We verify the input itself is NOT inside a div with opacity-50.
    // (Radix Select chevron may carry opacity-50 internally -- scope to divs only.)
    const dimmedDiv = Array.from(container.querySelectorAll('div.opacity-50'))
    expect(dimmedDiv).toHaveLength(0)
  })

  it('shows error toast when pause fails', async () => {
    mockPauseMutateAsync.mockRejectedValue(new Error('network error'))
    renderBuilder(makeConnector({
      interval_type: 'hours',
      interval_value: 6,
      schedule_enabled: true,
    }))

    const toggle = screen.getByRole('switch', { name: /Enable or disable automatic schedule/i })
    await act(async () => {
      fireEvent.click(toggle)
    })

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to update schedule',
          variant: 'destructive',
        })
      )
    })
  })
})

// ---------------------------------------------------------------------------
// UI-01 + UI-04 combined: Empty state and fire time preview visibility
// ---------------------------------------------------------------------------

describe('ScheduleBuilder — UI-01: Empty state', () => {
  beforeEach(() => {
    mockHasPermission = true
  })

  it('shows empty state text when no schedule is configured and no value entered', () => {
    renderBuilder(makeConnector({ interval_type: null, interval_value: null }))
    expect(screen.getByText('No schedule configured')).toBeDefined()
  })
})
