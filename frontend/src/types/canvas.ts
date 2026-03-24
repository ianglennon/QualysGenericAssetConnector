// Canvas-side type (short names for display)
export type MappingTypeUI = 'direct' | 'static' | 'conditional'
// API-side type (matches backend schema exactly)
export type MappingTypeAPI = 'direct_copy' | 'static_default' | 'conditional'
// StaticValue type selector
export type StaticValueType = 'string' | 'number' | 'boolean'

// Type translation functions
export function canvasTypeToAPI(t: MappingTypeUI): MappingTypeAPI {
  if (t === 'direct') return 'direct_copy'
  if (t === 'static') return 'static_default'
  return 'conditional'
}

export function apiTypeToCanvas(t: MappingTypeAPI | string): MappingTypeUI {
  if (t === 'direct_copy') return 'direct'
  if (t === 'static_default') return 'static'
  if (t === 'conditional') return 'conditional'
  return 'direct'  // safe fallback for unknown values
}

// Condition rule shape matching backend ConditionRule exactly
export interface CanvasConditionRule {
  operator: 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'ends_with' | 'regex' | 'in_list'
  source_field: string  // locked — same as edge.sourceHandle
  target_value: string  // match value
  value: string         // output when condition matches
}

// GET /connectors/{id}/fields/discover response
export interface FieldDiscoveryItem {
  path: string        // e.g. "address.city"
  type: string        // "string" | "number" | "boolean" | "array" | "null" | "object"
  sample_value: unknown
}

export interface DiscoverResponse {
  fields: FieldDiscoveryItem[]
  record_count: number
}

// GET /qualys/schema response
export interface QualysSchemaField {
  field: string       // e.g. "instanceUuidSource"
  is_identity: boolean
}

export interface QualysSchemaResponse {
  fields: QualysSchemaField[]
}

// Canvas draft state — lives only in component state, never persisted until Phase 9
// edge.source = NODE id ('source-panel'), edge.sourceHandle = field path
// edge.target = NODE id ('target-panel'), edge.targetHandle = Qualys field name
export interface DraftMapping {
  sourceField: string   // FieldDiscoveryItem.path
  targetField: string   // QualysSchemaField.field
  mappingType: MappingTypeUI  // defaults to 'direct'
}

// Node data shapes for React Flow custom nodes
export interface SourcePanelData {
  fields: FieldDiscoveryItem[]
  linkedSourceFields: Set<string>   // paths with an active edge
  linkedFieldOrder: Map<string, number>  // source field → sort position (matching target panel order)
}

export interface TargetPanelData {
  fields: QualysSchemaField[]
  linkedTargetFields: Set<string>   // field names with an active edge
  linkedFieldOrder: Map<string, number>  // target field → sort position (matching source panel order)
}

// Edge data shape for MappingEdge custom edge
// Index signature required by @xyflow/react EdgeBase<Record<string, unknown>> constraint
export interface MappingEdgeData extends Record<string, unknown> {
  mappingType: MappingTypeUI
  staticValue?: string | number | boolean
  valueType?: StaticValueType
  conditions?: CanvasConditionRule[]
  fallback?: string
}

// --- Chain Canvas types (Phase 42) ---

// Canvas API response (mirrors backend CanvasResponse)
export interface CanvasResponse {
  id: string
  connector_id: string
  name: string
  description: string | null
  is_enabled: boolean
  created_at: string
  updated_at: string
}

// Canvas-endpoint API response (mirrors backend CanvasEndpointResponse)
export interface CanvasEndpointResponse {
  id: string
  canvas_id: string
  endpoint_id: string
  parent_ref_id: string | null
  field_role: string
  variable_extractions: Record<string, string> | null
  max_concurrency: number
  tree_order: number
  created_at: string
  updated_at: string
}

// Canvas-endpoint create payload (mirrors backend CanvasEndpointCreate)
export interface CanvasEndpointCreate {
  endpoint_id: string
  parent_ref_id?: string | null
  field_role?: string
  variable_extractions?: Record<string, string> | null
  max_concurrency?: number
  tree_order?: number
}

// Canvas-endpoint update payload (mirrors backend CanvasEndpointUpdate)
export interface CanvasEndpointUpdate {
  parent_ref_id?: string | null
  field_role?: string | null
  variable_extractions?: Record<string, string> | null
  max_concurrency?: number | null
  tree_order?: number | null
}

// React Flow node data for EndpointNode custom node (per D-02, D-03, D-14)
export interface EndpointNodeData extends Record<string, unknown> {
  endpointId: string | null        // null for unsaved new endpoints
  canvasEndpointId: string | null   // null for unsaved
  name: string
  path: string
  fields: FieldDiscoveryItem[]
  parentRefId: string | null
  variableExtractions: Record<string, string> | null
  maxConcurrency: number
  isDiscovering: boolean
  discoveryError: string | null
}

// React Flow edge data for ChainEdge custom edge
export interface ChainEdgeData extends Record<string, unknown> {
  sourceField: string  // The parent field path that provides the variable
}
