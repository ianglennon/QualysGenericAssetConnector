import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { HttpDetailPanel } from './HttpDetailPanel'
import type { HttpRequestDetail, HttpResponseDetail } from '@/types/api'

// Mock clipboard API
beforeEach(() => {
  Object.assign(navigator, {
    clipboard: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  })
})

const mockRequest: HttpRequestDetail = {
  url: 'https://api.example.com/hosts',
  method: 'GET',
  headers: { 'Content-Type': 'application/json', 'Authorization': '[REDACTED]' },
  body: null,
}

const mockResponse: HttpResponseDetail = {
  status_code: 500,
  headers: { 'Content-Type': 'application/json' },
  body: '{"error":"internal server error"}',
}

describe('HttpDetailPanel', () => {
  // Test 1 (UI-02): Panel renders trigger and toggles
  it('renders "HTTP Details" trigger and toggles visibility on click', () => {
    render(<HttpDetailPanel httpRequest={mockRequest} />)
    const trigger = screen.getByText('HTTP Details')
    expect(trigger).toBeDefined()
    expect(trigger.getAttribute('aria-expanded')).toBe('false')

    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText('Request')).toBeDefined()
  })

  // Test 2 (UI-02): No trigger when both null
  it('does NOT render trigger when both httpRequest and httpResponse are null', () => {
    const { container } = render(
      <HttpDetailPanel httpRequest={null} httpResponse={null} />
    )
    expect(container.innerHTML).toBe('')
  })

  // Test 3 (UI-02): Only Request section when httpResponse is null
  it('renders only Request section when httpResponse is null', () => {
    render(<HttpDetailPanel httpRequest={mockRequest} httpResponse={null} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    expect(screen.getByText('Request')).toBeDefined()
    expect(screen.queryByText('Response')).toBeNull()
  })

  // Test 4 (UI-02): Only Response section when httpRequest is null
  it('renders only Response section when httpRequest is null', () => {
    render(<HttpDetailPanel httpRequest={null} httpResponse={mockResponse} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    expect(screen.getByText('Response')).toBeDefined()
    expect(screen.queryByText('Request')).toBeNull()
  })

  // Test 5 (UI-02): Both sections with separator
  it('renders both sections with separator when both request and response are provided', () => {
    render(<HttpDetailPanel httpRequest={mockRequest} httpResponse={mockResponse} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    expect(screen.getByText('Request')).toBeDefined()
    expect(screen.getByText('Response')).toBeDefined()
    expect(screen.getByRole('separator')).toBeDefined()
  })

  // Test 6 (UI-03): Copy request content
  it('copies serialized request content to clipboard', async () => {
    render(<HttpDetailPanel httpRequest={mockRequest} httpResponse={null} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    const copyButton = screen.getByTitle('Copy to clipboard')
    fireEvent.click(copyButton)

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      'GET https://api.example.com/hosts\nContent-Type: application/json\nAuthorization: [REDACTED]'
    )
  })

  // Test 7 (UI-03): Copy response content
  it('copies serialized response content to clipboard', async () => {
    render(<HttpDetailPanel httpRequest={null} httpResponse={mockResponse} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    const copyButton = screen.getByTitle('Copy to clipboard')
    fireEvent.click(copyButton)

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      'Status: 500\nContent-Type: application/json\n\n{\n  "error": "internal server error"\n}'
    )
  })

  // Test 8 (UI-04): JSON body is displayed with indented formatting
  it('displays JSON body with indented formatting', () => {
    render(<HttpDetailPanel httpRequest={null} httpResponse={mockResponse} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    const preBlock = screen.getByText(/\"error\": \"internal server error\"/)
    expect(preBlock.tagName).toBe('PRE')
    expect(preBlock.textContent).toContain('{\n  "error": "internal server error"\n}')
  })

  // Test 9 (UI-04): Non-JSON body is displayed as plain text
  it('displays non-JSON body as plain text', () => {
    const plainResponse: HttpResponseDetail = {
      status_code: 502,
      headers: { 'Content-Type': 'text/html' },
      body: '<html>Bad Gateway</html>',
    }
    render(<HttpDetailPanel httpRequest={null} httpResponse={plainResponse} />)
    fireEvent.click(screen.getByText('HTTP Details'))

    const preBlock = screen.getByText('<html>Bad Gateway</html>')
    expect(preBlock.tagName).toBe('PRE')
  })
})
