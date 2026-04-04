/**
 * Tests for ScheduleBadge component.
 *
 * UI-05: Schedule badge on ConnectorCard shows 3 states:
 *   - Active: green badge with interval label (e.g. "Every 6 hours")
 *   - Paused: amber badge showing "Paused"
 *   - No schedule: renders nothing
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import type { Connector } from '@/types/api'
import { ScheduleBadge } from './ScheduleBadge'

// Minimal connector fixture — only fields ScheduleBadge cares about
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

// ---------------------------------------------------------------------------
// UI-05: No schedule state — renders nothing
// ---------------------------------------------------------------------------

describe('ScheduleBadge — UI-05: No schedule configured', () => {
  it('renders nothing when interval_type is null', () => {
    const { container } = render(
      <ScheduleBadge connector={makeConnector({ interval_type: null })} />
    )
    expect(container.firstChild).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// UI-05: Paused state — amber "Paused" badge
// ---------------------------------------------------------------------------

describe('ScheduleBadge — UI-05: Paused schedule', () => {
  it('shows Paused badge when schedule_enabled is false and interval_type is set', () => {
    render(
      <ScheduleBadge
        connector={makeConnector({
          interval_type: 'hours',
          interval_value: 6,
          schedule_enabled: false,
        })}
      />
    )
    expect(screen.getByText('Paused')).toBeDefined()
  })

  it('Paused badge does not show active interval label', () => {
    render(
      <ScheduleBadge
        connector={makeConnector({
          interval_type: 'hours',
          interval_value: 6,
          schedule_enabled: false,
        })}
      />
    )
    expect(screen.queryByText(/Every/i)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// UI-05: Active state — green badge with interval label and next run
// ---------------------------------------------------------------------------

describe('ScheduleBadge — UI-05: Active schedule', () => {
  it('shows interval label "Every 6 hours" for plural value', () => {
    render(
      <ScheduleBadge
        connector={makeConnector({
          interval_type: 'hours',
          interval_value: 6,
          schedule_enabled: true,
        })}
      />
    )
    expect(screen.getByText('Every 6 hours')).toBeDefined()
  })

  it('uses singular form "Every 1 hour" for interval_value of 1', () => {
    render(
      <ScheduleBadge
        connector={makeConnector({
          interval_type: 'hours',
          interval_value: 1,
          schedule_enabled: true,
        })}
      />
    )
    expect(screen.getByText('Every 1 hour')).toBeDefined()
  })

  it('shows next run time when next_run_at is provided', () => {
    render(
      <ScheduleBadge
        connector={makeConnector({
          interval_type: 'hours',
          interval_value: 6,
          schedule_enabled: true,
          next_run_at: '2026-04-05T10:30:00Z',
        })}
      />
    )
    // Should contain "Next:" prefix
    const nextEl = screen.getByText(/Next:/i)
    expect(nextEl).toBeDefined()
  })

  it('does not show Paused badge when schedule is active', () => {
    render(
      <ScheduleBadge
        connector={makeConnector({
          interval_type: 'days',
          interval_value: 2,
          schedule_enabled: true,
        })}
      />
    )
    expect(screen.queryByText('Paused')).toBeNull()
  })
})
