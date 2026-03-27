import { useEffect, useState } from 'react'
import { useUpdateNodeInternals, useNodeId, Handle, Position } from '@xyflow/react'
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

function Separator({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-1 px-2 text-xs text-muted-foreground">
      <span className="flex-1 border-t" />
      <span>{label}</span>
      <span className="flex-1 border-t" />
    </div>
  )
}

export function TargetPanelNode({ data }: NodeProps & { data: TargetPanelData }) {
  const nodeId = useNodeId() ?? 'target-panel'
  const updateNodeInternals = useUpdateNodeInternals()
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  // Sort linked fields by edge index (matches source panel order → straight lines)
  const linkedFields = [...data.fields]
    .filter(f => data.linkedTargetFields.has(f.field))
    .sort((a, b) => {
      const posA = data.linkedFieldOrder?.get(a.field) ?? Infinity
      const posB = data.linkedFieldOrder?.get(b.field) ?? Infinity
      if (posA !== posB) return posA - posB
      return a.field.localeCompare(b.field)
    })

  const unlinkedFields = sortFields(
    data.fields.filter(f => !data.linkedTargetFields.has(f.field))
  )

  const customAttributes = data.customAttributes ?? []
  const linkedCustomAttrs = customAttributes
    .filter(f => data.linkedTargetFields.has(f.field))
    .sort((a, b) => {
      const posA = data.linkedFieldOrder?.get(a.field) ?? Infinity
      const posB = data.linkedFieldOrder?.get(b.field) ?? Infinity
      if (posA !== posB) return posA - posB
      return a.field.localeCompare(b.field)
    })
  const unlinkedCustomAttrs = customAttributes
    .filter(f => !data.linkedTargetFields.has(f.field))
    .sort((a, b) => a.field.localeCompare(b.field))
  const allCustomAttrs = [...linkedCustomAttrs, ...unlinkedCustomAttrs]

  // Re-register handle positions when fields change (initial load, seeding)
  useEffect(() => {
    if (data.fields.length > 0 || (data.customAttributes ?? []).length > 0) {
      requestAnimationFrame(() => updateNodeInternals(nodeId))
    }
  }, [data.fields, data.customAttributes, data.linkedTargetFields, data.linkedFieldOrder, nodeId, updateNodeInternals])

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
        <Separator label={`——— Linked (${linkedFields.length}) ———`} />

        <div className="transition-all duration-200">
          {linkedFields.length === 0 ? (
            <p className="text-xs text-muted-foreground italic px-3 py-1">
              (no connections yet)
            </p>
          ) : (
            linkedFields.map(field => (
              <div
                key={field.field}
                className="relative flex items-center gap-2 px-3 py-2 text-xs border-r-2 border-primary/40 bg-primary/5"
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={field.field}
                  isConnectable={false}
                  style={TARGET_HANDLE_STYLE}
                />
                <span className="flex-1 font-mono truncate">
                  {field.is_identity ? `★ ${field.field}` : field.field}
                </span>
                {field.is_identity && (
                  <span className="bg-amber-100 text-amber-700 text-xs px-1 rounded">
                    [IDENTITY]
                  </span>
                )}
              </div>
            ))
          )}
        </div>

        <Separator label={`——— Unlinked (${unlinkedFields.length}) ———`} />

        {unlinkedFields.map(field => (
          <div
            key={field.field}
            className="relative flex items-center gap-2 px-3 py-2 text-xs hover:bg-muted/30"
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
              <span className="bg-amber-100 text-amber-700 text-xs px-1 rounded">
                [IDENTITY]
              </span>
            )}
          </div>
        ))}

        <Separator label={`——— Custom Attributes (${customAttributes.length}) ———`} />

        {allCustomAttrs.length === 0 ? (
          <p className="text-xs text-muted-foreground italic px-3 py-2">
            No custom attributes defined. Click + Add custom attribute to map source fields to Qualys custom key-value pairs.
          </p>
        ) : (
          allCustomAttrs.map(field => {
            const isLinked = data.linkedTargetFields.has(field.field)
            const displayName = field.field.replace('customAttribute.', '')
            return (
              <div
                key={field.field}
                className={`relative flex items-center gap-2 px-3 py-2 text-xs ${
                  isLinked
                    ? 'border-r-2 border-violet-400 bg-violet-50'
                    : 'hover:bg-muted/30'
                }`}
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={field.field}
                  isConnectable={!isLinked}
                  style={TARGET_HANDLE_STYLE}
                />
                <span className="flex-1 font-mono truncate">{displayName}</span>
                <span className="bg-violet-100 text-violet-700 text-xs px-1 rounded">
                  [CUSTOM]
                </span>
                <button
                  className="text-muted-foreground hover:text-destructive p-0.5"
                  onClick={() => data.onRemoveCustomAttribute?.(field.field)}
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
          existingKeys={new Set(customAttributes.map(f => f.field))}
          onAdd={(key) => data.onAddCustomAttribute?.(key)}
          onClose={() => setAddDialogOpen(false)}
        />
      </div>
    </div>
  )
}
