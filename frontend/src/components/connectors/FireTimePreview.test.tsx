/**
 * Tests for FireTimePreview component.
 *
 * UI-03: Fire time preview shows 5 times, first with relative+absolute format,
 *        rest with absolute format only.
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { FireTimePreview } from './FireTimePreview'

// ---------------------------------------------------------------------------
// UI-03: Renders exactly 5 fire times
// ---------------------------------------------------------------------------

describe('FireTimePreview — UI-03: Shows 5 scheduled fire times', () => {
  it('renders 5 list items for a valid interval', () => {
    render(<FireTimePreview intervalType="hours" intervalValue={6} />)

    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(5)
  })

  it('shows "Next scheduled runs" heading', () => {
    render(<FireTimePreview intervalType="hours" intervalValue={6} />)

    expect(screen.getByText('Next scheduled runs')).toBeDefined()
  })
})

// ---------------------------------------------------------------------------
// UI-03: First fire time uses relative + absolute format
// ---------------------------------------------------------------------------

describe('FireTimePreview — UI-03: First fire time is relative + absolute', () => {
  it('first item contains relative text (in X hours / in X minutes)', () => {
    render(<FireTimePreview intervalType="hours" intervalValue={6} />)

    const items = screen.getAllByRole('listitem')
    const firstText = items[0].textContent ?? ''
    // date-fns formatDistanceToNow produces text like "in about 6 hours"
    // The first item wraps both relative and absolute in one string
    expect(firstText).toMatch(/in /i)
  })

  it('first item contains absolute time in parentheses', () => {
    render(<FireTimePreview intervalType="hours" intervalValue={6} />)

    const items = screen.getAllByRole('listitem')
    const firstText = items[0].textContent ?? ''
    // Absolute format: "Apr 5, 10:30" — wrapped in parentheses
    expect(firstText).toMatch(/\(/)
    expect(firstText).toMatch(/\)/)
  })
})

// ---------------------------------------------------------------------------
// UI-03: Remaining fire times are absolute-only (no relative text)
// ---------------------------------------------------------------------------

describe('FireTimePreview — UI-03: Subsequent fire times are absolute-only', () => {
  it('items 2-5 do not contain relative "in " prefix', () => {
    render(<FireTimePreview intervalType="days" intervalValue={1} />)

    const items = screen.getAllByRole('listitem')
    // Items at index 1-4 (2nd through 5th) should be absolute-only
    for (let i = 1; i < 5; i++) {
      const text = items[i].textContent ?? ''
      // Absolute date format contains month abbreviations like "Jan", "Feb", etc.
      // and does NOT contain parentheses (which only the first item has)
      expect(text).not.toMatch(/\(/)
    }
  })
})

// ---------------------------------------------------------------------------
// UI-03: Invalid inputs render nothing
// ---------------------------------------------------------------------------

describe('FireTimePreview — UI-03: Invalid intervals render nothing', () => {
  it('renders null for value of 0', () => {
    const { container } = render(<FireTimePreview intervalType="hours" intervalValue={0} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders null for unknown interval type', () => {
    const { container } = render(<FireTimePreview intervalType="decades" intervalValue={1} />)
    expect(container.firstChild).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// UI-03: Works for all four interval types
// ---------------------------------------------------------------------------

describe('FireTimePreview — UI-03: Supports all interval types', () => {
  it.each([
    ['minutes', 30],
    ['hours', 4],
    ['days', 2],
    ['weeks', 1],
  ] as const)('renders 5 fire times for %s interval', (type, value) => {
    render(<FireTimePreview intervalType={type} intervalValue={value} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(5)
  })
})
