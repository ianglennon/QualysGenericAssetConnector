import { useEffect } from 'react'
import { useUpdateNodeInternals, useNodeId, Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { SourcePanelData } from '@/types/canvas'

const TYPE_BADGE: Record<string, string> = {
  string: 'bg-blue-100 text-blue-700',
  number: 'bg-green-100 text-green-700',
  boolean: 'bg-purple-100 text-purple-700',
  array: 'bg-orange-100 text-orange-700',
  object: 'bg-gray-100 text-gray-600',
}

function typeBadgeClass(type: string): string {
  return TYPE_BADGE[type] ?? 'bg-gray-100 text-gray-500'
}

// Inline styles override React Flow's default handle CSS (6x6, transform: translate(50%,-50%))
// which pushes handles outside the container where overflow-x-hidden clips them.
const SOURCE_HANDLE_STYLE: React.CSSProperties = {
  right: 0,
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

export function SourcePanelNode({ data }: NodeProps & { data: SourcePanelData }) {
  const nodeId = useNodeId() ?? 'source-panel'
  const updateNodeInternals = useUpdateNodeInternals()

  // Sort linked fields by target panel position (eliminates line crossing)
  const linked = [...data.fields]
    .filter(f => data.linkedSourceFields.has(f.path))
    .sort((a, b) => {
      const posA = data.linkedFieldOrder?.get(a.path) ?? Infinity
      const posB = data.linkedFieldOrder?.get(b.path) ?? Infinity
      if (posA !== posB) return posA - posB
      return a.path.localeCompare(b.path)
    })

  const unlinked = [...data.fields]
    .filter(f => !data.linkedSourceFields.has(f.path))
    .sort((a, b) => a.path.localeCompare(b.path))

  // Re-register handle positions when fields change (initial load, discovery, seeding)
  useEffect(() => {
    if (data.fields.length > 0) {
      requestAnimationFrame(() => updateNodeInternals(nodeId))
    }
  }, [data.fields, data.linkedSourceFields, data.linkedFieldOrder, nodeId, updateNodeInternals])

  function handleScroll() {
    updateNodeInternals(nodeId)
  }

  return (
    <div className="flex flex-col h-full bg-card border rounded-lg shadow-sm">
      <div className="px-3 py-2 border-b font-semibold text-sm bg-muted/40">
        Source Fields
      </div>

      <div
        className={`nowheel overflow-y-auto overflow-x-hidden shrink-0 ${
          linked.length > 0
            ? 'shadow-[0_2px_4px_-1px_rgba(0,0,0,0.1)] dark:shadow-[0_2px_4px_-1px_rgba(255,255,255,0.06)]'
            : ''
        }`}
        style={{ pointerEvents: 'auto', maxHeight: 'calc(50% - 24px)' }}
        onScroll={handleScroll}
      >
        <Separator label={`——— Linked (${linked.length}) ———`} />

        <div className="transition-all duration-200">
          {linked.length === 0 ? (
            <p className="text-xs text-muted-foreground italic px-3 py-1">
              (no connections yet)
            </p>
          ) : (
            linked.map(field => (
              <div
                key={field.path}
                className="relative flex items-center gap-2 px-3 py-2 text-xs border-l-2 border-primary/40 bg-primary/5"
              >
                <span className="flex-1 font-mono truncate">{field.path}</span>
                <span className={`px-1 rounded text-[10px] font-medium ${typeBadgeClass(field.type)}`}>
                  {field.type}
                </span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={field.path}
                  isConnectable={false}
                  style={SOURCE_HANDLE_STYLE}
                />
              </div>
            ))
          )}
        </div>
      </div>

      {linked.length > 0 && unlinked.length > 0 && (
        <div className="border-t border-border my-1" />
      )}

      <div
        className="nowheel overflow-y-auto overflow-x-hidden flex-1 min-h-0"
        style={{ pointerEvents: 'auto' }}
        onScroll={handleScroll}
      >
        <Separator label={`——— Unlinked (${unlinked.length}) ———`} />

        {unlinked.map(field => (
          <div
            key={field.path}
            className="relative flex items-center gap-2 px-3 py-2 text-xs hover:bg-muted/30"
          >
            <span className="flex-1 font-mono truncate">{field.path}</span>
            <span className={`px-1 rounded text-[10px] font-medium ${typeBadgeClass(field.type)}`}>
              {field.type}
            </span>
            <Handle
              type="source"
              position={Position.Right}
              id={field.path}
              isConnectable={true}
              style={SOURCE_HANDLE_STYLE}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
