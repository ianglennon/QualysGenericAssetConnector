import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

/**
 * Compute left-to-right tree layout positions using dagre.
 * Only uses chain edges (parent-child) for layout, not mapping edges.
 * Uses node.measured dimensions when available, falls back to defaults.
 *
 * @param nodes - All React Flow nodes
 * @param edges - All React Flow edges (only 'chain' type used for layout)
 * @param direction - 'LR' (left-to-right) or 'TB' (top-to-bottom)
 * @returns Map of nodeId -> {x, y} positions
 */
export function getLayoutedPositions(
  nodes: Node[],
  edges: Edge[],
  direction = 'LR',
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: direction, nodesep: 24, ranksep: 48 })

  nodes.forEach((node) => {
    const width = node.measured?.width ?? 280
    const height = node.measured?.height ?? 400
    g.setNode(node.id, { width, height })
  })

  // Only use chain edges for layout (not mapping edges)
  edges
    .filter((e) => e.type === 'chain')
    .forEach((e) => g.setEdge(e.source, e.target))

  dagre.layout(g)

  const positions = new Map<string, { x: number; y: number }>()
  nodes.forEach((node) => {
    const pos = g.node(node.id)
    if (pos) {
      const width = node.measured?.width ?? 280
      const height = node.measured?.height ?? 400
      positions.set(node.id, { x: pos.x - width / 2, y: pos.y - height / 2 })
    }
  })
  return positions
}
