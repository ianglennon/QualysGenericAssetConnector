import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import type { Node, Edge } from '@xyflow/react'
import { useBaseDetection } from './useBaseDetection'

function makeEndpointNode(id: string, treeOrder?: number): Node {
  return {
    id,
    type: 'endpointNode',
    position: { x: 0, y: 0 },
    data: {
      endpointId: id,
      canvasEndpointId: id,
      name: `Endpoint ${id}`,
      path: '/api/test',
      fields: [],
      parentRefId: null,
      variableExtractions: null,
      maxConcurrency: 1,
      isDiscovering: false,
      discoveryError: null,
      exclusionRules: [],
      isBase: false,
      treeOrder: treeOrder ?? 0,
    },
  }
}

function makeMappingEdge(id: string, source: string, targetHandle: string): Edge {
  return {
    id,
    source,
    target: 'target-panel',
    targetHandle,
    type: 'mapping',
  }
}

function makeChainEdge(id: string, source: string, target: string): Edge {
  return {
    id,
    source,
    target,
    type: 'chain',
  }
}

describe('useBaseDetection', () => {
  it('returns null baseNodeId and hasIdentityFields=false when edges array is empty', () => {
    const nodes = [makeEndpointNode('node-1')]
    const edges: Edge[] = []
    const { result } = renderHook(() => useBaseDetection(nodes, edges))
    expect(result.current).toEqual({ baseNodeId: null, hasIdentityFields: false })
  })

  it('returns null baseNodeId and hasIdentityFields=false when no mapping edges have identity field targetHandles', () => {
    const nodes = [makeEndpointNode('node-1')]
    const edges = [makeMappingEdge('e1', 'node-1', 'someNonIdentityField')]
    const { result } = renderHook(() => useBaseDetection(nodes, edges))
    expect(result.current).toEqual({ baseNodeId: null, hasIdentityFields: false })
  })

  it('returns baseNodeId and hasIdentityFields=true when a node has a mapping edge with identity targetHandle', () => {
    const nodes = [makeEndpointNode('node-1', 0)]
    const edges = [makeMappingEdge('e1', 'node-1', 'hostName')]
    const { result } = renderHook(() => useBaseDetection(nodes, edges))
    expect(result.current).toEqual({ baseNodeId: 'node-1', hasIdentityFields: true })
  })

  it('returns the node with lowest treeOrder when multiple endpoint nodes have identity-mapped edges', () => {
    const nodes = [
      makeEndpointNode('node-a', 5),
      makeEndpointNode('node-b', 2),
      makeEndpointNode('node-c', 8),
    ]
    const edges = [
      makeMappingEdge('e1', 'node-a', 'ipAddress'),
      makeMappingEdge('e2', 'node-b', 'fqdn'),
      makeMappingEdge('e3', 'node-c', 'macAddress'),
    ]
    const { result } = renderHook(() => useBaseDetection(nodes, edges))
    expect(result.current).toEqual({ baseNodeId: 'node-b', hasIdentityFields: true })
  })

  it('ignores edges whose type is not mapping (e.g., chain edges)', () => {
    const nodes = [makeEndpointNode('node-1'), makeEndpointNode('node-2')]
    const edges = [
      makeChainEdge('c1', 'node-1', 'node-2'),
      makeMappingEdge('e1', 'node-2', 'hostName'),
    ]
    const { result } = renderHook(() => useBaseDetection(nodes, edges))
    // node-2 has the identity mapping, not node-1 (chain edge ignored)
    expect(result.current).toEqual({ baseNodeId: 'node-2', hasIdentityFields: true })
  })

  it('handles nodes with treeOrder undefined by treating as Infinity (sorted last)', () => {
    const nodeWithOrder = makeEndpointNode('node-a', 3)
    const nodeWithoutOrder = makeEndpointNode('node-b')
    // Remove treeOrder from node-b data
    delete (nodeWithoutOrder.data as Record<string, unknown>).treeOrder

    const nodes = [nodeWithoutOrder, nodeWithOrder]
    const edges = [
      makeMappingEdge('e1', 'node-a', 'serialNumber'),
      makeMappingEdge('e2', 'node-b', 'hardwareUuid'),
    ]
    const { result } = renderHook(() => useBaseDetection(nodes, edges))
    // node-a has treeOrder 3, node-b has undefined (Infinity) -> node-a wins
    expect(result.current).toEqual({ baseNodeId: 'node-a', hasIdentityFields: true })
  })
})
