import type { MappingType } from './api'

// Re-export for convenience — canvas code imports from canvas.ts not api.ts
export type { MappingType }

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
  mappingType: MappingType  // defaults to 'direct'
}

// Node data shapes for React Flow custom nodes
export interface SourcePanelData {
  fields: FieldDiscoveryItem[]
  linkedSourceFields: Set<string>   // paths with an active edge
}

export interface TargetPanelData {
  fields: QualysSchemaField[]
  linkedTargetFields: Set<string>   // field names with an active edge
}

// Edge data shape for MappingEdge custom edge
export interface MappingEdgeData {
  mappingType: MappingType
}
