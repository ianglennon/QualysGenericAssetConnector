import { useEffect, useState } from 'react'
import { useUpdateNodeInternals, useNodeId, useReactFlow, Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import { Plus, X } from 'lucide-react'
import type { TargetPanelData, QualysSchemaField } from '@/types/canvas'
import { AddCustomAttributeDialog } from './AddCustomAttributeDialog'

function sortFields(fields: QualysSchemaField[]): QualysSchemaField[] {
  return [...fields].sort((a, b) => {
    if (a.is_identity !== b.is_identity) return a.is_identity ? -1 : 1
    return a.field.localeCompare(b.field)
  })
}

// Inline styles override React Flow's default handle CSS (6x6, transform: translate(-50%,-50%))
// which pushes handles outside the container where overflow-x-hidden clips them.
const TARGET_HANDLE_STYLE: React.CSSProperties = {
  left: 0,
  top: '50%',
  transform: 'translateY(-50%)',
  width: 12,
  height: 12,
  background: 'hsl(var(--primary) / 0.6)',
  border: '2px solid hsl(var(--background))',
  borderRadius: '50%',
  zIndex: 10,
}

export function TargetPanelNode({ data }: NodeProps & { data: TargetPanelData }) {
  const nodeId = useNodeId() ?? 'target-panel'
  const updateNodeInternals = useUpdateNodeInternals()
  const { setEdges } = useReactFlow()
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  // Local custom attributes state — self-contained, no parent callback needed
  const [localCustomAttrs, setLocalCustomAttrs] = useState<QualysSchemaField[]>(
    data.customAttributes ?? []
  )

  // Sync from parent when data.customAttributes changes (reconstruct from saved mappings, reset)
  useEffect(() => {
    const parentAttrs = data.customAttributes ?? []
    setLocalCustomAttrs(parentAttrs)
  }, [data.customAttributes])

  function handleAddAttribute(key: string) {
    const field = `customAttribute.${key}`
    setLocalCustomAttrs(prev => {
      if (prev.some(f => f.field === field)) return prev
      return [...prev, { field, is_identity: false }]
    })
  }

  function handleRemoveAttribute(field: string) {
    setLocalCustomAttrs(prev => prev.filter(f => f.field !== field))
    setEdges(eds => eds.filter(e => e.targetHandle !== field))
  }

  // Mapped fields: merge schema + custom attrs, sorted by edge index
  const allMapped: Array<{ key: string; isIdentity: boolean; isCustom: boolean }> = []
  for (const f of data.fields) {
    if (data.linkedTargetFields.has(f.field)) {
      allMapped.push({ key: f.field, isIdentity: f.is_identity, isCustom: false })
    }
  }
  for (const f of localCustomAttrs) {
    if (data.linkedTargetFields.has(f.field)) {
      allMapped.push({ key: f.field, isIdentity: false, isCustom: true })
    }
  }
  allMapped.sort((a, b) => {
    const posA = data.linkedFieldOrder?.get(a.key) ?? Infinity
    const posB = data.linkedFieldOrder?.get(b.key) ?? Infinity
    if (posA !== posB) return posA - posB
    return a.key.localeCompare(b.key)
  })

  // Unmapped schema fields: identity first, then alphabetical
  const unmappedSchema = sortFields(
    data.fields.filter(f => !data.linkedTargetFields.has(f.field))
  )

  // Unmapped custom attributes
  const unmappedCustom = localCustomAttrs
    .filter(f => !data.linkedTargetFields.has(f.field))
    .sort((a, b) => a.field.localeCompare(b.field))

  // Re-register handle positions when fields change (initial load, seeding)
  useEffect(() => {
    if (data.fields.length > 0 || localCustomAttrs.length > 0) {
      requestAnimationFrame(() => updateNodeInternals(nodeId))
    }
  }, [data.fields, localCustomAttrs, data.linkedTargetFields, data.linkedFieldOrder, nodeId, updateNodeInternals])

  function handleScroll() {
    updateNodeInternals(nodeId)
  }

  return (
    <div className="flex flex-col h-full bg-card border rounded-lg shadow-sm">
      <div className="px-3 py-2 border-b font-semibold text-sm bg-muted/40">
        Qualys Target Fields
      </div>

      <div
        className="nowheel overflow-y-auto overflow-x-hidden flex-1"
        style={{ pointerEvents: 'auto' }}
        onScroll={handleScroll}
      >
        {/* Mapped fields at the top (schema + custom merged) */}
        {allMapped.length === 0 ? (
          <p className="text-xs text-muted-foreground italic px-3 py-1">
            (no connections yet)
          </p>
        ) : (
          allMapped.map(item => {
            if (item.isCustom) {
              const displayName = item.key.replace('customAttribute.', '')
              return (
                <div
                  key={item.key}
                  className="relative flex items-center gap-2 px-3 py-2 text-xs border-r-2 border-violet-400 bg-violet-50 dark:bg-violet-950/40"
                >
                  <Handle
                    type="target"
                    position={Position.Left}
                    id={item.key}
                    isConnectable={false}
                    style={TARGET_HANDLE_STYLE}
                  />
                  <span className="flex-1 font-mono truncate">{displayName}</span>
                  <span className="bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300 text-xs px-1 rounded">
                    [CUSTOM]
                  </span>
                  <button
                    className="text-muted-foreground hover:text-destructive p-0.5"
                    onClick={() => handleRemoveAttribute(item.key)}
                    title="Remove custom attribute"
                    aria-label="Remove custom attribute"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              )
            }
            return (
              <div
                key={item.key}
                className="relative flex items-center gap-2 px-3 py-2 text-xs border-r-2 border-primary/40 bg-primary/5"
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={item.key}
                  isConnectable={false}
                  style={TARGET_HANDLE_STYLE}
                />
                <span className="flex-1 font-mono truncate">
                  {item.isIdentity ? `★ ${item.key}` : item.key}
                </span>
                {item.isIdentity && (
                  <span className="bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300 text-xs px-1 rounded">
                    [IDENTITY]
                  </span>
                )}
              </div>
            )
          })
        )}

        {/* Thin divider between mapped and unmapped */}
        {allMapped.length > 0 && (unmappedSchema.length > 0 || unmappedCustom.length > 0) && (
          <div className="border-t border-border my-1" />
        )}

        {/* Unmapped schema fields dimmed below */}
        {unmappedSchema.map(field => (
          <div
            key={field.field}
            className="relative flex items-center gap-2 px-3 py-2 text-xs hover:bg-muted/30 opacity-60"
          >
            <Handle
              type="target"
              position={Position.Left}
              id={field.field}
              isConnectable={true}
              style={TARGET_HANDLE_STYLE}
            />
            <span className="flex-1 font-mono truncate">
              {field.is_identity ? `★ ${field.field}` : field.field}
            </span>
            {field.is_identity && (
              <span className="bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300 text-xs px-1 rounded">
                [IDENTITY]
              </span>
            )}
          </div>
        ))}

        {/* Custom Attributes section */}
        {(localCustomAttrs.length > 0 || unmappedCustom.length === 0) && (
          <div className="px-3 py-1 text-xs font-medium text-muted-foreground">Custom Attributes</div>
        )}

        {unmappedCustom.length === 0 && localCustomAttrs.length === 0 ? (
          <p className="text-xs text-muted-foreground italic px-3 py-2 opacity-60">
            No custom attributes defined. Click + Add custom attribute to map source fields to Qualys custom key-value pairs.
          </p>
        ) : (
          unmappedCustom.map(field => {
            const displayName = field.field.replace('customAttribute.', '')
            return (
              <div
                key={field.field}
                className="relative flex items-center gap-2 px-3 py-2 text-xs hover:bg-muted/30 opacity-60"
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={field.field}
                  isConnectable={true}
                  style={TARGET_HANDLE_STYLE}
                />
                <span className="flex-1 font-mono truncate">{displayName}</span>
                <span className="bg-violet-100 text-violet-700 dark:bg-violet-900 dark:text-violet-300 text-xs px-1 rounded">
                  [CUSTOM]
                </span>
                <button
                  className="text-muted-foreground hover:text-destructive p-0.5"
                  onClick={() => handleRemoveAttribute(field.field)}
                  title="Remove custom attribute"
                  aria-label="Remove custom attribute"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )
          })
        )}

        {/* Add custom attribute button */}
        <button
          className="flex items-center gap-1 px-3 py-2 text-xs text-muted-foreground hover:text-foreground w-full text-left"
          onClick={() => setAddDialogOpen(true)}
        >
          <Plus className="h-3 w-3" />
          + Add custom attribute
        </button>

        <AddCustomAttributeDialog
          open={addDialogOpen}
          existingKeys={new Set(localCustomAttrs.map(f => f.field))}
          onAdd={(key) => {
            handleAddAttribute(key)
            setAddDialogOpen(false)
          }}
          onClose={() => setAddDialogOpen(false)}
        />
      </div>
    </div>
  )
}
