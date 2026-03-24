import { describe, it, expect } from 'vitest'
import type { Edge } from '@xyflow/react'
import { wouldCreateCycle } from './cycle-detection'

describe('wouldCreateCycle', () => {
  const makeChainEdge = (source: string, target: string): Edge => ({
    id: `${source}-${target}`,
    source,
    target,
    type: 'chain',
  })

  const makeMappingEdge = (source: string, target: string): Edge => ({
    id: `${source}-${target}`,
    source,
    target,
    type: 'mapping',
  })

  it('returns false for empty edge list', () => {
    expect(wouldCreateCycle('A', 'B', [])).toBe(false)
  })

  it('returns false for a valid parent-child connection (A -> B)', () => {
    const edges = [makeChainEdge('A', 'B')]
    expect(wouldCreateCycle('B', 'C', edges)).toBe(false)
  })

  it('returns true when connection would create direct cycle (A -> B, propose B -> A)', () => {
    const edges = [makeChainEdge('A', 'B')]
    expect(wouldCreateCycle('B', 'A', edges)).toBe(true)
  })

  it('returns true when connection would create indirect cycle (A -> B -> C, propose C -> A)', () => {
    const edges = [makeChainEdge('A', 'B'), makeChainEdge('B', 'C')]
    expect(wouldCreateCycle('C', 'A', edges)).toBe(true)
  })

  it('returns true for self-loop (A -> A)', () => {
    expect(wouldCreateCycle('A', 'A', [])).toBe(true)
  })

  it('ignores mapping edges when checking for cycles', () => {
    const edges = [makeMappingEdge('A', 'B')]
    expect(wouldCreateCycle('B', 'A', edges)).toBe(false)
  })

  it('handles deep chains without false positives (A -> B -> C -> D, propose D -> E)', () => {
    const edges = [
      makeChainEdge('A', 'B'),
      makeChainEdge('B', 'C'),
      makeChainEdge('C', 'D'),
    ]
    expect(wouldCreateCycle('D', 'E', edges)).toBe(false)
  })
})
