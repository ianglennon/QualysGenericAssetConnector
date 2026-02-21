export interface ApiError {
  code: string
  message: string
  details?: unknown
}

// Field Mapping Types
export type MappingType = 'direct' | 'static' | 'conditional'

export interface ConditionRule {
  field: string
  operator: string
  value: any
  then_value: any
  else_value?: any
}

export interface FieldMapping {
  id: string
  connector_id: string
  source_field: string
  target_field: string
  mapping_type: MappingType
  static_value?: string
  conditions?: ConditionRule[]
  order: number
  created_at: string
}

export interface FieldMappingCreate {
  connector_id: string
  source_field?: string
  target_field: string
  mapping_type: MappingType
  static_value?: string
  conditions?: ConditionRule[]
  order?: number
}

export interface PreviewRequest {
  connector_id: string
  sample_data: any
  mappings: FieldMappingCreate[]
}

export interface PreviewResponse {
  transformed: any
  warnings: string[]
}

// Connector Types
export type AuthMethod = 'bearer_token' | 'basic_auth' | 'api_key_header'

export interface CursorPagination {
  strategy_type: 'cursor'
  cursor_param: string
  next_cursor_path: string
  page_size_param?: string
}

export interface OffsetPagination {
  strategy_type: 'offset'
  limit_param: string
  offset_param: string
}

export interface PageNumberPagination {
  strategy_type: 'page_number'
  page_param: string
  page_size_param?: string
}

export interface LinkHeaderPagination {
  strategy_type: 'link_header'
  page_size_param?: string
}

export type PaginationStrategy = CursorPagination | OffsetPagination | PageNumberPagination | LinkHeaderPagination

export interface Connector {
  id: string
  name: string
  base_url: string
  test_path?: string
  auth_method: AuthMethod
  has_token: boolean
  has_username: boolean
  has_password: boolean
  has_api_key: boolean
  api_key_name?: string
  pagination_strategies: PaginationStrategy[]
  source_retry_limit?: number
  qualys_retry_limit?: number
  created_at: string
  updated_at: string
}

export interface ConnectorCredentials {
  token?: string
  username?: string
  password?: string
  api_key_name?: string
  api_key?: string
}

export interface ConnectorCreate {
  name: string
  base_url: string
  test_path?: string
  auth_method: AuthMethod
  credentials?: ConnectorCredentials
  pagination_strategies: PaginationStrategy[]
  source_retry_limit?: number
  qualys_retry_limit?: number
}

export interface TestConnectionResponse {
  success: boolean
  status_code?: number
  error?: string
  sample_data?: any
}

// Run History Types
export type RunStatus = 'success' | 'partial_success' | 'failed'

export interface RunHistory {
  id: string
  connector_id: string
  connector_name: string
  status: RunStatus
  started_at: string
  ended_at?: string
  records_fetched: number
  records_submitted: number
  records_failed: number
  error_message?: string
  error_details?: any
  request_payload?: any
  request_headers?: any
  response_body?: any
  response_headers?: any
}

export interface RunHistoryList {
  items: RunHistory[]
  total: number
  cursor?: string
}
