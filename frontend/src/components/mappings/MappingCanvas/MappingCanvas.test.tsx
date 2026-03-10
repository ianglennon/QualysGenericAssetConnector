import { describe, it, vi, expect } from 'vitest'
import React from 'react'
import { render, screen } from '@testing-library/react'
import { SourcePanelNode } from './SourcePanelNode'
import { TargetPanelNode } from './TargetPanelNode'
import { applyConnect, isValidConnection } from './MappingCanvas'
import type { Edge, Connection } from '@xyflow/react'

// These stubs are RED until Plans 02 and 03 implement the components.
// They define the behavioral contracts upfront.

vi.mock('@/hooks/queries/useDiscoverFields', () => ({
  useDiscoverFields: vi.fn(() => ({
    data: {
      fields: [
        { path: 'address.city', type: 'string', sample_value: 'Austin' },
        { path: 'hostname', type: 'string', sample_value: 'server-01' },
      ],
      record_count: 1,
    },
    isLoading: false,
    isError: false,
  })),
}))

vi.mock('@/hooks/queries/useQualysSchema', () => ({
  useQualysSchema: vi.fn(() => ({
    data: {
      fields: [
        { field: 'instanceUuidSource', is_identity: true },
        { field: 'name', is_identity: false },
        { field: 'address', is_identity: false },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}))

// Stub ReactFlow to avoid canvas complexity in unit tests
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="react-flow">{children}</div>
  ),
  ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  useNodesState: () => [[], vi.fn(), vi.fn()],
  useEdgesState: () => [[], vi.fn(), vi.fn()],
  useReactFlow: () => ({ deleteElements: vi.fn() }),
  useUpdateNodeInternals: () => vi.fn(),
  useNodeId: () => 'source-panel',
  Handle: ({ id }: { id?: string }) => <div data-testid="handle" data-id={id} />,
  Position: { Left: 'left', Right: 'right' },
  BaseEdge: () => <path />,
  EdgeLabelRenderer: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  getSmoothStepPath: () => ['M0,0', 50, 50],
  Background: () => null,
  BackgroundVariant: { Dots: 'dots' },
  addEdge: vi.fn((edge: Connection, edges: Edge[]) => [...edges, edge as Edge]),
}))

const mockSourceFields = [
  { path: 'address.city', type: 'string', sample_value: 'Austin' },
  { path: 'hostname', type: 'string', sample_value: 'server-01' },
]

const mockTargetFields = [
  { field: 'instanceUuidSource', is_identity: true },
  { field: 'name', is_identity: false },
  { field: 'address', is_identity: false },
]

const minimalNodeProps = {
  id: 'source-panel',
  type: 'sourcePanel',
  xPos: 0,
  yPos: 0,
  zIndex: 0,
  isConnectable: true,
  dragging: false,
  selected: false,
  draggable: false,
  selectable: false,
  deletable: false,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
}

describe('SourcePanelNode', () => {
  it('displays "Source Fields" header', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText('Source Fields')).toBeInTheDocument()
  })

  it('shows unlinked field paths', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText('hostname')).toBeInTheDocument()
    expect(screen.getByText('address.city')).toBeInTheDocument()
  })

  it('shows "Linked (0)" separator when no connections', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText(/Linked \(0\)/)).toBeInTheDocument()
  })

  it('shows "(no connections yet)" placeholder in empty linked zone', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set() }}
      />
    )
    expect(screen.getByText('(no connections yet)')).toBeInTheDocument()
  })

  it('moves field to linked zone when in linkedSourceFields', () => {
    render(
      <SourcePanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockSourceFields, linkedSourceFields: new Set(['hostname']) }}
      />
    )
    expect(screen.getByText(/Linked \(1\)/)).toBeInTheDocument()
    expect(screen.getByText(/Unlinked \(1\)/)).toBeInTheDocument()
  })
})

describe('TargetPanelNode', () => {
  it('displays "Qualys Target Fields" header', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText('Qualys Target Fields')).toBeInTheDocument()
  })

  it('identity fields (is_identity: true) sort to top of target panel', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    const items = screen.getAllByText(/instanceUuidSource|name|address/)
    // instanceUuidSource (identity) should appear before name and address
    const idxIdentity = items.findIndex(el => el.textContent?.includes('instanceUuidSource'))
    const idxName = items.findIndex(el => el.textContent === 'name')
    const idxAddress = items.findIndex(el => el.textContent === 'address')
    expect(idxIdentity).toBeLessThan(idxName)
    expect(idxIdentity).toBeLessThan(idxAddress)
  })

  it('identity fields display star prefix', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText('★ instanceUuidSource')).toBeInTheDocument()
  })

  it('identity fields display [IDENTITY] badge', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText('[IDENTITY]')).toBeInTheDocument()
  })

  it('shows "Linked (0)" separator on empty canvas', () => {
    render(
      <TargetPanelNode
        {...minimalNodeProps as any}
        data={{ fields: mockTargetFields, linkedTargetFields: new Set() }}
      />
    )
    expect(screen.getByText(/Linked \(0\)/)).toBeInTheDocument()
  })
})

describe('MappingCanvas', () => {
  it.todo('renders canvas shell without crashing')
  it.todo('linked/unlinked separator shows correct count after connection is added')
  it.todo('breaking a connection returns fields to unlinked zone')
})

describe('connection logic', () => {
  it('applyConnect adds edge with mappingType=direct', () => {
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'address.city',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [])
    expect(result).toHaveLength(1)
    expect((result[0] as any).data?.mappingType).toBe('direct')
  })

  it('applyConnect replaces existing edge from same source handle', () => {
    const existing: Edge = {
      id: '1',
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'name',
      data: { mappingType: 'direct' },
    }
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [existing])
    expect(result).toHaveLength(1)
    expect((result[0] as any).data?.mappingType).toBe('direct')
    expect(result[0].targetHandle).toBe('address')
  })

  it('applyConnect replaces existing edge to same target handle', () => {
    const existing: Edge = {
      id: '2',
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'address',
      data: { mappingType: 'direct' },
    }
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'address.city',
      targetHandle: 'address',
    }
    const result = applyConnect(connection, [existing])
    expect(result).toHaveLength(1)
    expect(result[0].sourceHandle).toBe('address.city')
  })

  it('isValidConnection returns false for self-loop (source === target)', () => {
    const connection: Connection = {
      source: 'source-panel',
      target: 'source-panel',
      sourceHandle: 'hostname',
      targetHandle: 'hostname',
    }
    expect(isValidConnection(connection)).toBe(false)
  })

  it('isValidConnection returns true for valid source→target connection', () => {
    const connection: Connection = {
      source: 'source-panel',
      target: 'target-panel',
      sourceHandle: 'hostname',
      targetHandle: 'name',
    }
    expect(isValidConnection(connection)).toBe(true)
  })
})
