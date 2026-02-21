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
export interface Connector {
  id: string
  name: string
  base_url: string
  auth_method: string
  is_valid_mappings: boolean
  created_at: string
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
