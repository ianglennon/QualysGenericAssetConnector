import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, vi, expect, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QualysConfigForm } from './QualysConfigForm'

// --- Module-level mocks ---

const mockMutate = vi.fn()

const mockUseQualysConfig = vi.fn(() => ({
  data: undefined,
  isLoading: false,
}))

const mockUseUpdateQualysConfig = vi.fn(() => ({
  mutate: mockMutate,
  isPending: false,
}))

vi.mock('@/hooks/queries/useQualys', () => ({
  useQualysConfig: () => mockUseQualysConfig(),
  useUpdateQualysConfig: () => mockUseUpdateQualysConfig(),
}))

const mockToast = vi.fn()
vi.mock('@/hooks/use-toast', () => ({
  toast: (...args: any[]) => mockToast(...args),
  useToast: vi.fn(() => ({ toast: mockToast })),
}))

// --- Test wrapper ---

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// --- Tests ---

describe('QualysConfigForm — field presence (UI-01)', () => {
  beforeEach(() => {
    mockMutate.mockClear()
    mockToast.mockClear()
    mockUseQualysConfig.mockReturnValue({ data: undefined, isLoading: false })
    mockUseUpdateQualysConfig.mockReturnValue({ mutate: mockMutate, isPending: false })
  })

  it('renders the username field', () => {
    render(<QualysConfigForm />, { wrapper: makeWrapper() })
    expect(screen.getByLabelText(/username/i)).toBeTruthy()
  })

  it('renders the password field', () => {
    render(<QualysConfigForm />, { wrapper: makeWrapper() })
    expect(screen.getByLabelText(/password/i)).toBeTruthy()
  })

  it('renders the connector_uuid field', () => {
    render(<QualysConfigForm />, { wrapper: makeWrapper() })
    expect(screen.getByLabelText(/connector uuid/i)).toBeTruthy()
  })

  it('renders exactly 3 input fields (username, password, connector_uuid)', () => {
    render(<QualysConfigForm />, { wrapper: makeWrapper() })
    const inputs = screen.getAllByRole('textbox')
    // textbox role covers text inputs; password inputs have role=textbox in some implementations
    // We also check by querying all inputs directly
    const allInputs = document.querySelectorAll('input')
    expect(allInputs).toHaveLength(3)
  })

  it('does NOT render an api_url field', () => {
    render(<QualysConfigForm />, { wrapper: makeWrapper() })
    expect(screen.queryByLabelText(/api url/i)).toBeNull()
    expect(screen.queryByLabelText(/api_url/i)).toBeNull()
  })

  it('does NOT render a token/bearer token field', () => {
    render(<QualysConfigForm />, { wrapper: makeWrapper() })
    expect(screen.queryByLabelText(/bearer token/i)).toBeNull()
    expect(screen.queryByLabelText(/^token$/i)).toBeNull()
  })
})

describe('QualysConfigForm — QUALYS_INVALID_USERNAME inline error (UI-01)', () => {
  beforeEach(() => {
    mockMutate.mockClear()
    mockToast.mockClear()
    mockUseQualysConfig.mockReturnValue({ data: undefined, isLoading: false })
  })

  it('shows inline error under username field when mutation responds with QUALYS_INVALID_USERNAME', async () => {
    // Capture the onError callback from mutate and invoke it with the error
    mockMutate.mockImplementation((_payload: any, options: any) => {
      options?.onError?.({
        response: {
          data: {
            error: {
              code: 'QUALYS_INVALID_USERNAME',
              message: 'Username does not contain a valid Qualys platform identifier',
            },
          },
        },
      })
    })
    mockUseUpdateQualysConfig.mockReturnValue({ mutate: mockMutate, isPending: false })

    render(<QualysConfigForm />, { wrapper: makeWrapper() })

    // Fill in the form and submit
    await userEvent.type(screen.getByLabelText(/username/i), 'invaliduser')
    await userEvent.type(screen.getByLabelText(/password/i), 'somepass')
    await userEvent.type(screen.getByLabelText(/connector uuid/i), 'some-uuid')

    await userEvent.click(screen.getByRole('button', { name: /save configuration/i }))

    // The inline error should appear under the username field
    await waitFor(() => {
      expect(
        screen.getByText('Username does not contain a valid Qualys platform identifier')
      ).toBeTruthy()
    })
  })
})

describe('QualysConfigForm — platform info section (UI-02)', () => {
  const mockConfig = {
    id: 'cfg-1',
    username: 'quays2ab1',
    connector_uuid: 'abc-123',
    has_password: true,
    platform_name: 'US2',
    api_server_url: 'https://qualysapi.qg2.apps.qualys.com',
    api_gateway_url: 'https://gateway.qg2.apps.qualys.com',
  }

  beforeEach(() => {
    mockMutate.mockClear()
    mockToast.mockClear()
    mockUseUpdateQualysConfig.mockReturnValue({ mutate: mockMutate, isPending: false })
  })

  it('renders the "Detected Platform" heading when config exists', () => {
    mockUseQualysConfig.mockReturnValue({ data: mockConfig, isLoading: false })

    render(<QualysConfigForm />, { wrapper: makeWrapper() })

    expect(screen.getByText('Detected Platform')).toBeTruthy()
  })

  it('renders platform_name value when config exists', () => {
    mockUseQualysConfig.mockReturnValue({ data: mockConfig, isLoading: false })

    render(<QualysConfigForm />, { wrapper: makeWrapper() })

    expect(screen.getByText('US2')).toBeTruthy()
  })

  it('renders api_server_url value when config exists', () => {
    mockUseQualysConfig.mockReturnValue({ data: mockConfig, isLoading: false })

    render(<QualysConfigForm />, { wrapper: makeWrapper() })

    expect(screen.getByText('https://qualysapi.qg2.apps.qualys.com')).toBeTruthy()
  })

  it('renders api_gateway_url value when config exists', () => {
    mockUseQualysConfig.mockReturnValue({ data: mockConfig, isLoading: false })

    render(<QualysConfigForm />, { wrapper: makeWrapper() })

    expect(screen.getByText('https://gateway.qg2.apps.qualys.com')).toBeTruthy()
  })

  it('does NOT render platform info section when config is absent', () => {
    mockUseQualysConfig.mockReturnValue({ data: undefined, isLoading: false })

    render(<QualysConfigForm />, { wrapper: makeWrapper() })

    expect(screen.queryByText('Detected Platform')).toBeNull()
  })
})
