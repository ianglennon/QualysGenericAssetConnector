// Canvas-side type (short names for display)
export type MappingTypeUI = 'direct' | 'static' | 'conditional' | 'collect'
// API-side type (matches backend schema exactly)
export type MappingTypeAPI = 'direct_copy' | 'static_default' | 'conditional' | 'collect'
// StaticValue type selector
export type StaticValueType = 'string' | 'number' | 'boolean'

// Collect mapping configuration
export interface CollectConfig {
  array_path: string
  extract_field?: string
  filter?: { field: string; operator: string; value: string }
  separator?: string
}

// Type translation functions
export function canvasTypeToAPI(t: MappingTypeUI): MappingTypeAPI {
  if (t === 'direct') return 'direct_copy'
  if (t === 'static') return 'static_default'
  if (t === 'collect') return 'collect'
  return 'conditional'
}

export function apiTypeToCanvas(t: MappingTypeAPI | string): MappingTypeUI {
  if (t === 'direct_copy') return 'direct'
  if (t === 'static_default') return 'static'
  if (t === 'conditional') return 'conditional'
  if (t === 'collect') return 'collect'
  return 'direct'  // safe fallback for unknown values
}

// Condition rule shape matching backend ConditionRule exactly
export interface CanvasConditionRule {
  operator: 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'ends_with' | 'regex' | 'in_list'
  source_field: string  // locked — same as edge.sourceHandle
  target_value: string  // match value
  value: string         // output when condition matches
}

// Exclusion rule for canvas endpoint filtering (Phase 47)
export interface ExclusionRule {
  source_field: string
  operator: 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'ends_with' | 'regex' | 'in_list'
  value: string
}

// GET /connectors/{id}/fields/discover response
export interface FieldDiscoveryItem {
  path: string        // e.g. "address.city"
  type: string        // "string" | "number" | "boolean" | "array" | "null" | "object"
  sample_value: unknown
  is_array_child?: boolean       // true for fields inside an array
  parent_array_path?: string     // path to the parent array (for pre-filling collect mappings)
  is_array_parent?: boolean      // true for array-type fields themselves
}

export interface DiscoverResponse {
  fields: FieldDiscoveryItem[]
  record_count: number
  auto_detected_data_root?: string | null
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
  customAttributes?: QualysSchemaField[]    // custom attribute target fields
}

// Edge data shape for MappingEdge custom edge
// Index signature required by @xyflow/react EdgeBase<Record<string, unknown>> constraint
export interface MappingEdgeData extends Record<string, unknown> {
  mappingType: MappingTypeUI
  staticValue?: string | number | boolean
  valueType?: StaticValueType
  conditions?: CanvasConditionRule[]
  fallback?: string
  collectConfig?: CollectConfig
}

// --- Chain Canvas types (Phase 42) ---

/** Enriched canvas response with aggregation fields for card grid (from Plan 01 CanvasListResponse). */
export interface CanvasListItem {
  id: string
  connector_id: string
  name: string
  description: string | null
  is_enabled: boolean
  base_canvas_endpoint_id: string | null
  endpoint_count: number
  field_mapping_count: number
  last_run_status: string | null
  last_run_at: string | null
  created_at: string
  updated_at: string
}

/** Payload for PATCH /connectors/{id}/canvases/{canvasId} */
export interface CanvasUpdate {
  name?: string
  description?: string
  is_enabled?: boolean
}

// Canvas API response (mirrors backend CanvasResponse)
export interface CanvasResponse {
  id: string
  connector_id: string
  name: string
  description: string | null
  is_enabled: boolean
  base_canvas_endpoint_id: string | null
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
  exclusion_rules: ExclusionRule[] | null
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
  exclusion_rules?: ExclusionRule[] | null
}

// Canvas-endpoint update payload (mirrors backend CanvasEndpointUpdate)
export interface CanvasEndpointUpdate {
  parent_ref_id?: string | null
  field_role?: string | null
  variable_extractions?: Record<string, string> | null
  max_concurrency?: number | null
  tree_order?: number | null
  exclusion_rules?: ExclusionRule[] | null
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
  exclusionRules: ExclusionRule[]
  isBase: boolean  // true if this endpoint is the detected base (Phase 57)
  treeOrder: number  // tree_order from API, used by useBaseDetection for BFS ordering
  linkedSourceFields?: Set<string>
  linkedFieldOrder?: Map<string, number>
}

// React Flow edge data for ChainEdge custom edge
export interface ChainEdgeData extends Record<string, unknown> {
  sourceField: string  // The parent field path that provides the variable
}
