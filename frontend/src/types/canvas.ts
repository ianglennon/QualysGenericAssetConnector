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
  collectConfig?: CollectConfig
}
