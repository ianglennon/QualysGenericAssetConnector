import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import RunDetailPage from './RunDetailPage'

// Mock react-router-dom useParams
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: 'run-1' }),
  }
})

const baseLog = {
  id: 'log-1',
  run_id: 'run-1',
  endpoint_id: 'ep-1',
  endpoint_name: 'Test Endpoint',
  endpoint_path: '/api/hosts',
  execution_order: 1,
  records_fetched: 10,
  records_submitted: 8,
  records_failed: 2,
  status: 'failed',
  error_message: 'Connection refused',
  created_at: '2026-03-18T10:00:00Z',
}

const failedSourceFetch = {
  ...baseLog,
  failure_stage: 'source_fetch',
  http_request: {
    url: 'https://api.example.com/hosts',
    method: 'GET',
    headers: { Authorization: '[REDACTED]' },
    body: null,
  },
  http_response: null,
}

const failedTransformation = {
  ...baseLog,
  id: 'log-2',
  failure_stage: 'transformation',
  http_request: null,
  http_response: null,
}

const failedQualysSubmit = {
  ...baseLog,
  id: 'log-3',
  failure_stage: 'qualys_submit',
  http_request: null,
  http_response: null,
}

const failedNoStage = {
  ...baseLog,
  id: 'log-4',
  failure_stage: null,
  http_request: null,
  http_response: null,
}

const successLog = {
  ...baseLog,
  id: 'log-5',
  status: 'success',
  error_message: undefined,
  failure_stage: null,
  http_request: null,
  http_response: null,
}

function makeMockRun(endpointLogs: typeof baseLog[]) {
  return {
    id: 'run-1',
    connector_id: 'conn-1',
    connector_name: 'Test Connector',
    status: 'failed',
    started_at: '2026-03-18T10:00:00Z',
    finished_at: '2026-03-18T10:01:00Z',
    records_fetched: 10,
    records_submitted: 8,
    records_failed: 2,
    error_message: null,
    endpoint_logs: endpointLogs,
  }
}

// Mock useRun hook - will be configured per test
const mockUseRun = vi.fn()
vi.mock('@/hooks/queries/useRuns', () => ({
  useRun: (...args: unknown[]) => mockUseRun(...args),
  useRuns: vi.fn(() => ({ data: null, isLoading: false })),
  useTriggerRun: vi.fn(() => ({ mutate: vi.fn() })),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <RunDetailPage />
    </MemoryRouter>
  )
}

describe('RunDetailPage - Stage Badge', () => {
  // Test 1 (UI-01): failure_stage="source_fetch" renders "Source Fetch" badge
  it('renders "Source Fetch" stage badge for source_fetch failure', () => {
    mockUseRun.mockReturnValue({
      data: makeMockRun([failedSourceFetch]),
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText('Source Fetch')).toBeDefined()
  })

  // Test 2 (UI-01): failure_stage="transformation" renders "Transformation" badge
  it('renders "Transformation" stage badge for transformation failure', () => {
    mockUseRun.mockReturnValue({
      data: makeMockRun([failedTransformation]),
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText('Transformation')).toBeDefined()
  })

  // Test 3 (UI-01): failure_stage="qualys_submit" renders "Qualys Submit" badge
  it('renders "Qualys Submit" stage badge for qualys_submit failure', () => {
    mockUseRun.mockReturnValue({
      data: makeMockRun([failedQualysSubmit]),
      isLoading: false,
    })
    renderPage()
    expect(screen.getByText('Qualys Submit')).toBeDefined()
  })

  // Test 4 (UI-01): failure_stage=null renders no stage badge
  it('does not render a stage badge when failure_stage is null', () => {
    mockUseRun.mockReturnValue({
      data: makeMockRun([failedNoStage]),
      isLoading: false,
    })
    renderPage()
    expect(screen.queryByText('Source Fetch')).toBeNull()
    expect(screen.queryByText('Transformation')).toBeNull()
    expect(screen.queryByText('Qualys Submit')).toBeNull()
  })

  // Test 5 (UI-01): Successful endpoint shows no stage badge
  it('does not render a stage badge for successful endpoint logs', () => {
    mockUseRun.mockReturnValue({
      data: makeMockRun([successLog]),
      isLoading: false,
    })
    renderPage()
    expect(screen.queryByText('Source Fetch')).toBeNull()
    expect(screen.queryByText('Transformation')).toBeNull()
    expect(screen.queryByText('Qualys Submit')).toBeNull()
  })

  // Test 6: HttpDetailPanel is rendered when http_request is present
  it('renders HttpDetailPanel when http_request is present', () => {
    mockUseRun.mockReturnValue({
      data: makeMockRun([failedSourceFetch]),
      isLoading: false,
    })
    renderPage()
    // HttpDetailPanel renders an "HTTP Details" trigger button when data exists
    expect(screen.getByText('HTTP Details')).toBeDefined()
  })
})
