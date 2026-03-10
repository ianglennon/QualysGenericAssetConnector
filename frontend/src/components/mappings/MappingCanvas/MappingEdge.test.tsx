import { describe, it, vi, expect, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Edge, EdgeProps } from '@xyflow/react'
import type { MappingEdgeData } from '@/types/canvas'
import type { MappingEdgeType } from './MappingEdge'

// ---- shared mock data ----
const mockSetEdges = vi.fn()
const mockDeleteElements = vi.fn()
const mockGetEdge = vi.fn()

vi.mock('@xyflow/react', () => ({
  useReactFlow: () => ({
    deleteElements: mockDeleteElements,
    setEdges: mockSetEdges,
    getEdge: mockGetEdge,
  }),
  BaseEdge: () => <path />,
  EdgeLabelRenderer: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  getSmoothStepPath: () => ['M0,0', 50, 50],
  Position: { Left: 'left', Right: 'right' },
}))

// Stub Radix UI Select portal for testing (avoids portal issues)
vi.mock('@radix-ui/react-select', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@radix-ui/react-select')>()
  return {
    ...actual,
    Portal: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  }
})

// Stub Radix UI Dialog portal for testing
vi.mock('@radix-ui/react-dialog', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@radix-ui/react-dialog')>()
  return {
    ...actual,
    Portal: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  }
})

// Stub Radix UI Popover portal for testing
vi.mock('@radix-ui/react-popover', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@radix-ui/react-popover')>()
  return {
    ...actual,
    Portal: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  }
})

function makeEdgeProps(data: MappingEdgeData, id = 'edge-1'): EdgeProps<MappingEdgeType> {
  return {
    id,
    source: 'source-panel',
    target: 'target-panel',
    sourceX: 0,
    sourceY: 0,
    targetX: 100,
    targetY: 100,
    sourcePosition: 'right' as any,
    targetPosition: 'left' as any,
    data,
    selected: false,
    animated: false,
    interactionWidth: 20,
    markerStart: undefined,
    markerEnd: undefined,
    style: undefined,
    label: undefined,
    labelStyle: undefined,
    labelShowBg: false,
    labelBgStyle: undefined,
    labelBgPadding: [0, 0],
    labelBgBorderRadius: 0,
    pathOptions: undefined,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGetEdge.mockReturnValue({ sourceHandle: 'hostname' })
})

describe('MappingEdge badge interactions', () => {
  it('left-click cycles type: direct → static → conditional → direct', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'direct' })} />)
    const badge = screen.getByText('direct')
    fireEvent.click(badge)
    expect(mockSetEdges).toHaveBeenCalledTimes(1)
    // Verify cycleType was called — the updater function advances to 'static'
    const updater = mockSetEdges.mock.calls[0][0]
    const fakeEdges: Edge[] = [{ id: 'edge-1', source: '', target: '', data: { mappingType: 'direct' } }]
    const result = updater(fakeEdges)
    expect(result[0].data?.mappingType).toBe('static')
  })

  it('left-click from conditional wraps back to direct', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'conditional' })} />)
    const badge = screen.getByText(/conditional/)
    fireEvent.click(badge)
    const updater = mockSetEdges.mock.calls[0][0]
    const fakeEdges: Edge[] = [{ id: 'edge-1', source: '', target: '', data: { mappingType: 'conditional' } }]
    const result = updater(fakeEdges)
    expect(result[0].data?.mappingType).toBe('direct')
  })

  it('left-click clears staticValue and conditions on type change', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static', staticValue: 'hello', conditions: [] })} />)
    const badge = screen.getByText(/static/)
    fireEvent.click(badge)
    const updater = mockSetEdges.mock.calls[0][0]
    const fakeEdges: Edge[] = [{ id: 'edge-1', source: '', target: '', data: { mappingType: 'static', staticValue: 'hello', conditions: [] } }]
    const result = updater(fakeEdges)
    expect(result[0].data?.staticValue).toBeUndefined()
    expect(result[0].data?.conditions).toEqual([])
  })

  it('right-click on static badge opens StaticValueEditor', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static' })} />)
    const badge = screen.getByText(/static/)
    fireEvent.contextMenu(badge)
    // StaticValueEditor should be visible
    expect(screen.getByText(/Save/i)).toBeInTheDocument()
  })

  it('right-click on direct badge does NOT open any editor', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'direct' })} />)
    const badge = screen.getByText('direct')
    fireEvent.contextMenu(badge)
    expect(screen.queryByText(/Save/i)).not.toBeInTheDocument()
  })

  it('badge shows unconfigured style when staticValue is undefined on static type', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static' })} />)
    const badge = screen.getByText('static')
    expect(badge.className).toContain('bg-muted')
  })

  it('badge shows configured style (checkmark) when staticValue is set on static type', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static', staticValue: 'hello', valueType: 'string' })} />)
    const badge = screen.getByText(/static.*✓/)
    expect(badge.className).toContain('bg-primary')
  })
})

describe('StaticValueEditor', () => {
  it('save button calls setEdges with updated staticValue and valueType', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static' })} />)
    // Open the editor
    fireEvent.contextMenu(screen.getByText(/static/))
    // Type a value
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'my-value' } })
    // Click Save
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(mockSetEdges).toHaveBeenCalled()
    // Verify the updater sets staticValue
    const updater = mockSetEdges.mock.calls[mockSetEdges.mock.calls.length - 1][0]
    const fakeEdges: Edge[] = [{ id: 'edge-1', source: '', target: '', data: { mappingType: 'static' } }]
    const result = updater(fakeEdges)
    expect(result[0].data?.staticValue).toBe('my-value')
  })

  it('cancel button calls onCancel without updating edge data', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static' })} />)
    fireEvent.contextMenu(screen.getByText(/static/))
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    // setEdges should NOT have been called after cancel (only the badge click would call it)
    const setEdgesCallCount = mockSetEdges.mock.calls.length
    expect(setEdgesCallCount).toBe(0)
  })

  it('boolean type shows true/false dropdown instead of text input', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'static', valueType: 'boolean' })} />)
    fireEvent.contextMenu(screen.getByText(/static/))
    // Should not have a plain text input for boolean
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    // Should have a combobox (Select) for the value
    const comboboxes = screen.getAllByRole('combobox')
    // At minimum 2: type selector + value selector
    expect(comboboxes.length).toBeGreaterThanOrEqual(2)
  })
})

describe('ConditionalEditor', () => {
  it('right-click on conditional badge opens ConditionalEditor', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'conditional' })} />)
    fireEvent.contextMenu(screen.getByText(/conditional/))
    expect(screen.getByText(/Add condition/i)).toBeInTheDocument()
  })

  it('cancel button calls onCancel without updating edge data', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'conditional' })} />)
    fireEvent.contextMenu(screen.getByText(/conditional/))
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockSetEdges).not.toHaveBeenCalled()
  })

  it('Add condition button appends a new empty row', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'conditional', conditions: [] })} />)
    fireEvent.contextMenu(screen.getByText(/conditional/))
    const addBtn = screen.getByRole('button', { name: /add condition/i })
    fireEvent.click(addBtn)
    // After adding, there should be at least one operator select
    const inputs = screen.getAllByRole('combobox')
    // At least one operator combobox should appear
    expect(inputs.length).toBeGreaterThanOrEqual(1)
  })

  it('save button calls setEdges with updated conditions', async () => {
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'conditional', conditions: [] })} />)
    fireEvent.contextMenu(screen.getByText(/conditional/))
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(mockSetEdges).toHaveBeenCalled()
    const updater = mockSetEdges.mock.calls[mockSetEdges.mock.calls.length - 1][0]
    const fakeEdges: Edge[] = [{ id: 'edge-1', source: '', target: '', data: { mappingType: 'conditional' } }]
    const result = updater(fakeEdges)
    expect(result[0].data).toHaveProperty('conditions')
  })

  it('source field label is read-only (same as edge sourceHandle)', async () => {
    mockGetEdge.mockReturnValue({ sourceHandle: 'address.city' })
    const { MappingEdge } = await import('./MappingEdge')
    render(<MappingEdge {...makeEdgeProps({ mappingType: 'conditional' })} />)
    fireEvent.contextMenu(screen.getByText(/conditional/))
    expect(screen.getByText('address.city')).toBeInTheDocument()
  })
})
