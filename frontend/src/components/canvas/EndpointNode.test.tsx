import { describe, it, vi, expect, beforeAll } from 'vitest'
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { EndpointNode } from './EndpointNode'

beforeAll(() => {
  class MockResizeObserver {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  global.ResizeObserver = MockResizeObserver as any
})

// Mock @xyflow/react — EndpointNode uses useNodeId, useUpdateNodeInternals, Handle, Position
vi.mock('@xyflow/react', () => ({
  useUpdateNodeInternals: () => vi.fn(),
  useNodeId: () => 'test-node-id',
  Handle: ({ id, type }: { id?: string; type?: string }) => (
    <div data-testid="handle" data-id={id} data-type={type} />
  ),
  Position: { Left: 'left', Right: 'right' },
}))

// Minimal required NodeProps fields
const baseNodeProps = {
  id: 'test-node-id',
  type: 'endpointNode',
  xPos: 0,
  yPos: 0,
  zIndex: 0,
  isConnectable: true,
  dragging: false,
  selected: false,
  draggable: true,
  selectable: true,
  deletable: true,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
}

function makeData(overrides = {}) {
  return {
    endpointId: 'ep-1',
    canvasEndpointId: 'ce-1',
    name: 'Test Endpoint',
    path: '/api/test',
    fields: [],
    parentRefId: null,
    variableExtractions: null,
    maxConcurrency: 5,
    isDiscovering: false,
    discoveryError: null,
    onNameChange: vi.fn(),
    onPathChange: vi.fn(),
    onDiscoverFields: vi.fn(),
    onDelete: vi.fn(),
    onMaxConcurrencyChange: vi.fn(),
    ...overrides,
  }
}

describe('EndpointNode', () => {
  describe('CUI-03: Concurrency limit configuration', () => {
    it('renders max concurrency input with default value of 5', () => {
      const data = makeData()
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      expect(screen.getByText('Max Concurrency')).toBeInTheDocument()
      // The concurrency input shows the current value
      const concurrencyInput = screen.getByPlaceholderText('5')
      expect(concurrencyInput).toBeInTheDocument()
      // Value should be 5
      expect((concurrencyInput as HTMLInputElement).value).toBe('5')
    })

    it('calls onMaxConcurrencyChange when concurrency input changes', () => {
      const onMaxConcurrencyChange = vi.fn()
      const data = makeData({ onMaxConcurrencyChange, maxConcurrency: 5 })
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      const concurrencyInput = screen.getByPlaceholderText('5')
      fireEvent.change(concurrencyInput, { target: { value: '10' } })

      expect(onMaxConcurrencyChange).toHaveBeenCalledWith(10)
    })

    it('enforces minimum concurrency value of 1 via minus button', () => {
      const onMaxConcurrencyChange = vi.fn()
      // Set concurrency to 1 — clicking minus should NOT fire callback (would go below 1)
      const data = makeData({ onMaxConcurrencyChange, maxConcurrency: 1 })
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      // Find the minus button (renders the minus character)
      const minusButton = screen.getByRole('button', { name: '−' })
      fireEvent.click(minusButton)

      // onMaxConcurrencyChange should NOT be called because 1 - 1 = 0 < 1
      expect(onMaxConcurrencyChange).not.toHaveBeenCalled()
    })
  })

  describe('Endpoint node rendering', () => {
    it('renders editable name and path inputs', () => {
      const data = makeData({ name: '', path: '' })
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      expect(screen.getByPlaceholderText('Endpoint name')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('/api/path')).toBeInTheDocument()
    })

    it('renders Discover Fields button', () => {
      const data = makeData()
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      expect(screen.getByText('Discover Fields')).toBeInTheDocument()
    })

    it('shows field list with type badges and handles after discovery', () => {
      const fields = [
        { path: 'hostname', type: 'string', sample_value: 'server-01' },
        { path: 'count', type: 'number', sample_value: 42 },
      ]
      const data = makeData({ fields })
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      // Type badges
      expect(screen.getByText('string')).toBeInTheDocument()
      expect(screen.getByText('number')).toBeInTheDocument()
      // Field paths
      expect(screen.getByText('hostname')).toBeInTheDocument()
      expect(screen.getByText('count')).toBeInTheDocument()
      // Source handles rendered for each field
      const handles = screen.getAllByTestId('handle')
      const sourceHandles = handles.filter(
        (h) => h.getAttribute('data-type') === 'source'
      )
      expect(sourceHandles.length).toBeGreaterThanOrEqual(fields.length)
    })

    it('renders delete button with correct aria-label', () => {
      const data = makeData()
      render(<EndpointNode {...(baseNodeProps as any)} data={data} />)

      expect(screen.getByRole('button', { name: 'Delete endpoint' })).toBeInTheDocument()
    })
  })
})
