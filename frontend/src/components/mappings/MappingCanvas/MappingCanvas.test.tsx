import { describe, it, vi } from 'vitest'
import React from 'react'

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
  Handle: () => <div data-testid="handle" />,
  Position: { Left: 'left', Right: 'right' },
  BaseEdge: () => <path />,
  EdgeLabelRenderer: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  getSmoothStepPath: () => ['M0,0', 50, 50],
  Background: () => null,
  BackgroundVariant: { Dots: 'dots' },
  addEdge: vi.fn((edge, edges) => [...edges, edge]),
}))

describe('MappingCanvas', () => {
  it.todo('renders canvas shell without crashing')
  it.todo('SourcePanelNode displays "Source Fields" header')
  it.todo('TargetPanelNode displays "Qualys Target Fields" header')
  it.todo('identity fields (is_identity: true) sort to top of target panel')
  it.todo('identity fields display star prefix and [IDENTITY] badge')
  it.todo('linked/unlinked separator shows "Linked (0)" on empty canvas')
  it.todo('linked/unlinked separator shows correct count after connection is added')
  it.todo('breaking a connection returns fields to unlinked zone')
})
