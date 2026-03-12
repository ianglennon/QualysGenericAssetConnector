export interface ApiError {
  code: string
  message: string
  details?: unknown
}

// Field Mapping Types
export type MappingType = 'direct' | 'static' | 'conditional'         // canvas-side short names
export type MappingTypeAPI = 'direct_copy' | 'static_default' | 'conditional'  // API-side type strings

export interface ConditionRule {
  operator: 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'ends_with' | 'regex' | 'in_list'
  source_field: string   // the locked source field path
  target_value: string   // the match value the operator compares against
  value: string          // output value when condition matches
}

export interface FieldMapping {
  id: string
  endpoint_id: string
  source_field: string
  target_field: string
  mapping_type: MappingTypeAPI
  static_value?: string
  conditions?: ConditionRule[]
  fallback?: string
  order: number
  created_at: string
}

export interface FieldMappingCreate {
  endpoint_id?: string
  source_field?: string
  target_field: string
  mapping_type: MappingTypeAPI   // use API type strings when calling the API
  static_value?: string
  conditions?: ConditionRule[]
  fallback?: string              // optional fallback for conditional
  order?: number
}

export interface BatchReplaceResponse {
  replaced: number
  is_valid_mappings: boolean
  validation_errors: string[]
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

// Connector Endpoint Types
export interface ConnectorEndpoint {
  id: string
  connector_id: string
  name: string
  path: string
  pagination_config: Record<string, unknown> | null
  is_enabled: boolean
  display_order: number
  created_at: string
  updated_at: string
}

export interface EndpointCreate {
  name: string
  path: string
  pagination_config?: Record<string, unknown>
  is_enabled?: boolean
  display_order?: number
}

export interface EndpointRunLog {
  id: string
  run_id: string
  endpoint_id: string
  endpoint_name?: string
  endpoint_path?: string
  execution_order: number
  records_fetched: number
  records_submitted: number
  records_failed: number
  status: string
  error_message?: string
  created_at: string
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
  has_valid_endpoints: boolean
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
export type RunStatus = 'success' | 'partial_success' | 'failed' | 'running'

export interface RunHistory {
  id: string
  connector_id: string
  connector_name: string
  status: RunStatus
  started_at: string
  finished_at?: string
  records_fetched: number
  records_submitted: number
  records_failed: number
  error_message?: string
  error_details?: any
  request_payload?: any
  request_headers?: any
  response_body?: any
  response_headers?: any
  endpoint_logs: EndpointRunLog[]
}

export interface RunHistoryList {
  items: RunHistory[]
  total: number
  cursor?: string
}

// Qualys Configuration Types
export interface QualysConfig {
  id: string
  api_url: string
  username: string
  connector_uuid: string
  has_password: boolean
  has_token: boolean
}

export interface QualysConfigUpdate {
  api_url: string
  username: string
  connector_uuid: string
  password?: string
  token?: string
}

// Theme and User Profile Types
export type ThemeMode = 'light' | 'dark' | 'black' | 'high-contrast' | 'deuteranopia' | 'protanopia' | 'tritanopia' | 'custom'

export interface CustomTheme {
  name: string
  colors: Record<string, string>
}

export interface UserPreferences {
  theme: ThemeMode
  custom_theme?: CustomTheme
  font_size?: 'normal' | 'large' | 'x-large'
  reduced_motion?: boolean
}

export interface PasswordChangeRequest {
  current_password: string
  new_password: string
}

export interface Session {
  id: string
  ip_address: string
  user_agent: string
  created_at: string
  last_active: string
}
