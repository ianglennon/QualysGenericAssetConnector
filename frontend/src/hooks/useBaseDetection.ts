import { useMemo } from 'react'
import type { Node, Edge } from '@xyflow/react'
import { IDENTITY_FIELDS } from '@/constants/canvas'
import type { EndpointNodeData } from '@/types/canvas'

interface BaseDetectionResult {
  baseNodeId: string | null
  hasIdentityFields: boolean
}

/**
 * Detects the base endpoint node on the canvas by finding the endpoint
 * with the lowest treeOrder that has at least one identity-mapped edge.
 *
 * Mirrors backend detection logic in backend/app/services/detection.py
 * but runs client-side for real-time visual feedback.
 */
export function useBaseDetection(nodes: Node[], edges: Edge[]): BaseDetectionResult {
  return useMemo(() => {
    // 1. Filter to mapping edges with identity field targetHandles
    const identityEdges = edges.filter(
      (e) => e.type === 'mapping' && e.targetHandle != null && IDENTITY_FIELDS.has(e.targetHandle)
    )

    if (identityEdges.length === 0) {
      return { baseNodeId: null, hasIdentityFields: false }
    }

    // 2. Collect unique source node IDs from identity edges
    const identitySourceIds = new Set(identityEdges.map((e) => e.source))

    // 3. Filter to endpoint nodes that are identity sources
    const candidates = nodes.filter(
      (n) => n.type === 'endpointNode' && identitySourceIds.has(n.id)
    )

    // 4. Sort by treeOrder ascending (undefined treated as Infinity)
    candidates.sort((a, b) => {
      const orderA = (a.data as EndpointNodeData).treeOrder ?? Infinity
      const orderB = (b.data as EndpointNodeData).treeOrder ?? Infinity
      return orderA - orderB
    })

    return {
      baseNodeId: candidates[0]?.id ?? null,
      hasIdentityFields: true,
    }
  }, [nodes, edges])
}
