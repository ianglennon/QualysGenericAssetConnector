import { describe, it, vi, beforeAll } from 'vitest'

// These stubs are RED/SKIPPED until Plan 02 implements EndpointNode.
// They define the behavioral contracts upfront for CUI-03.

beforeAll(() => {
  class MockResizeObserver {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  global.ResizeObserver = MockResizeObserver as any
})

describe('EndpointNode', () => {
  describe('CUI-03: Concurrency limit configuration', () => {
    it.skip('renders max concurrency input with default value of 5', () => {
      // Verify: number input with value 5, label "Max Concurrency"
    })

    it.skip('calls onMaxConcurrencyChange when concurrency input changes', () => {
      // Verify: callback fires with new numeric value
    })

    it.skip('enforces minimum concurrency value of 1', () => {
      // Verify: input has min=1 attribute
    })
  })

  describe('Endpoint node rendering', () => {
    it.skip('renders editable name and path inputs', () => {
      // Verify: two input fields with correct placeholders
    })

    it.skip('renders Discover Fields button', () => {
      // Verify: button with text "Discover Fields" exists
    })

    it.skip('shows field list with type badges and handles after discovery', () => {
      // Verify: fields render with type badge colors and right-side Handle elements
    })

    it.skip('renders delete button with correct aria-label', () => {
      // Verify: button with aria-label="Delete endpoint" exists
    })
  })
})
