import { describe, it } from 'vitest'

describe('MappingEdge badge interactions', () => {
  it.todo('left-click cycles type: direct → static → conditional → direct')
  it.todo('right-click on static badge opens StaticValueEditor')
  it.todo('right-click on conditional badge opens ConditionalEditor')
  it.todo('badge shows unconfigured style when staticValue is undefined on static type')
  it.todo('badge shows configured style (checkmark) when staticValue is set on static type')
})

describe('StaticValueEditor', () => {
  it.todo('save button calls onSave with value and type')
  it.todo('cancel button calls onCancel without updating edge data')
  it.todo('boolean type shows true/false dropdown instead of text input')
})

describe('ConditionalEditor', () => {
  it.todo('save button calls onSave with conditions array')
  it.todo('cancel button calls onCancel without updating edge data')
  it.todo('Add condition button appends a new empty row')
  it.todo('source field label is read-only (same as edge sourceHandle)')
})
