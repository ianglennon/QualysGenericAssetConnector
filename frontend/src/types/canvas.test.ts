import { describe, it, expect } from 'vitest'
import { canvasTypeToAPI, apiTypeToCanvas } from './canvas'

describe('canvasTypeToAPI', () => {
  it('translates direct to direct_copy', () => {
    expect(canvasTypeToAPI('direct')).toBe('direct_copy')
  })
  it('translates static to static_default', () => {
    expect(canvasTypeToAPI('static')).toBe('static_default')
  })
  it('translates conditional to conditional', () => {
    expect(canvasTypeToAPI('conditional')).toBe('conditional')
  })
})

describe('apiTypeToCanvas', () => {
  it('translates direct_copy to direct', () => {
    expect(apiTypeToCanvas('direct_copy')).toBe('direct')
  })
  it('translates static_default to static', () => {
    expect(apiTypeToCanvas('static_default')).toBe('static')
  })
  it('translates conditional to conditional', () => {
    expect(apiTypeToCanvas('conditional')).toBe('conditional')
  })
  it('returns direct for unknown values', () => {
    expect(apiTypeToCanvas('unknown_type')).toBe('direct')
  })
})
