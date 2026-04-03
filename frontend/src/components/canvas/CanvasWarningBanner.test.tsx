import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CanvasWarningBanner } from './CanvasWarningBanner'
import { IDENTITY_FIELDS } from '@/constants/canvas'

describe('CanvasWarningBanner', () => {
  it('renders nothing when visible=false', () => {
    const { container } = render(<CanvasWarningBanner visible={false} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders alert with role="alert" when visible=true', () => {
    render(<CanvasWarningBanner visible={true} />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('renders title text "No base endpoint detected"', () => {
    render(<CanvasWarningBanner visible={true} />)
    expect(screen.getByText('No base endpoint detected')).toBeInTheDocument()
  })

  it('renders all 11 identity field names in the description', () => {
    render(<CanvasWarningBanner visible={true} />)
    for (const field of IDENTITY_FIELDS) {
      expect(screen.getByRole('alert').textContent).toContain(field)
    }
  })

  it('renders AlertTriangle icon (svg element present)', () => {
    render(<CanvasWarningBanner visible={true} />)
    const alert = screen.getByRole('alert')
    const svg = alert.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })
})
