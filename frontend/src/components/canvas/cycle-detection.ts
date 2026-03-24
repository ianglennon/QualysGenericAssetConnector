import type { Edge } from '@xyflow/react'

/**
 * Check if adding a chain edge from sourceId to targetId would create a cycle.
 * Mirrors backend detect_cycle() for instant drag-time validation.
 * Only considers edges with type === 'chain' (not mapping edges).
 *
 * @returns true if the proposed connection would create a cycle
 */
export function wouldCreateCycle(
  sourceId: string,
  targetId: string,
  edges: Edge[],
): boolean {
  // Self-loop is always a cycle
  if (sourceId === targetId) return true

  // Build parent map from chain edges: child -> parent
  const parentMap = new Map<string, string>()
  edges
    .filter((e) => e.type === 'chain')
    .forEach((e) => parentMap.set(e.target, e.source))

  // Walk up from source, checking if we reach target (which would mean target is an ancestor of source)
  const visited = new Set<string>()
  let current: string | undefined = sourceId
  while (current !== undefined) {
    if (current === targetId) return true
    if (visited.has(current)) return false
    visited.add(current)
    current = parentMap.get(current)
  }
  return false
}
