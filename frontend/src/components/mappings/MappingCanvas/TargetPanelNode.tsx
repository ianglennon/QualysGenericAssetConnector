import { useUpdateNodeInternals, useNodeId, Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { TargetPanelData, QualysSchemaField } from '@/types/canvas'

function sortFields(fields: QualysSchemaField[]): QualysSchemaField[] {
  return [...fields].sort((a, b) => {
    if (a.is_identity !== b.is_identity) return a.is_identity ? -1 : 1
    return a.field.localeCompare(b.field)
  })
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

  const linkedFields = sortFields(
    data.fields.filter(f => data.linkedTargetFields.has(f.field))
  )

  const unlinkedFields = sortFields(
    data.fields.filter(f => !data.linkedTargetFields.has(f.field))
  )

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
                className="relative flex items-center gap-2 px-3 py-1 text-xs border-r-2 border-primary/40 bg-primary/5"
              >
                <Handle
                  type="target"
                  position={Position.Left}
                  id={field.field}
                  isConnectable={false}
                  style={{ left: -8 }}
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
            className="relative flex items-center gap-2 px-3 py-1 text-xs hover:bg-muted/30"
          >
            <Handle
              type="target"
              position={Position.Left}
              id={field.field}
              isConnectable={true}
              style={{ left: -8 }}
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
      </div>
    </div>
  )
}
