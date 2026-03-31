import { useEffect } from 'react'
import { useUpdateNodeInternals, useNodeId, Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import type { SourcePanelData } from '@/types/canvas'
import { typeBadgeClass } from '@/lib/field-type-colors'

function getAncestorDepth(path: string): number {
  let depth = 0
  let p = path
  while (p.startsWith('_parent.')) {
    depth++
    p = p.slice('_parent.'.length)
  }
  return depth
}

const DEPTH_LABELS: Record<number, string> = {
  1: 'Parent Fields',
  2: 'Grandparent Fields',
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

export function SourcePanelNode({ data }: NodeProps & { data: SourcePanelData }) {
  const nodeId = useNodeId() ?? 'source-panel'
  const updateNodeInternals = useUpdateNodeInternals()

  // Mapped fields sorted by edge index (eliminates line crossing)
  const mapped = data.fields
    .filter(f => data.linkedSourceFields.has(f.path))
    .sort((a, b) => {
      const posA = data.linkedFieldOrder?.get(a.path) ?? Infinity
      const posB = data.linkedFieldOrder?.get(b.path) ?? Infinity
      if (posA !== posB) return posA - posB
      return a.path.localeCompare(b.path)
    })

  // Unmapped fields grouped by ancestor depth
  const unmapped = data.fields.filter(f => !data.linkedSourceFields.has(f.path))
  const unmappedByDepth = new Map<number, typeof data.fields>()
  for (const field of unmapped) {
    const depth = getAncestorDepth(field.path)
    if (!unmappedByDepth.has(depth)) unmappedByDepth.set(depth, [])
    unmappedByDepth.get(depth)!.push(field)
  }
  for (const [, fields] of unmappedByDepth) {
    fields.sort((a, b) => a.path.localeCompare(b.path))
  }
  const unmappedDepths = [...unmappedByDepth.keys()].sort((a, b) => a - b)

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
        className="nowheel overflow-y-auto overflow-x-hidden flex-1"
        style={{ pointerEvents: 'auto' }}
        onScroll={handleScroll}
      >
        {/* Mapped fields at the top */}
        {mapped.length === 0 ? (
          <p className="text-xs text-muted-foreground italic px-3 py-1">
            (no connections yet)
          </p>
        ) : (
          mapped.map(field => {
            const displayPath = field.is_array_child
              ? '.' + field.path.split('[].').pop()
              : field.path
            return (
              <div
                key={field.path}
                className={`relative flex items-center gap-2 px-3 py-2 text-xs border-l-2 ${
                  field.is_array_child
                    ? 'pl-4 border-orange-300 dark:border-orange-500 bg-primary/5'
                    : 'border-primary/40 bg-primary/5'
                }`}
              >
                <span className="flex-1 font-mono truncate">{displayPath}</span>
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
            )
          })
        )}

        {/* Thin divider between mapped and unmapped */}
        {mapped.length > 0 && unmapped.length > 0 && (
          <div className="border-t border-border my-1" />
        )}

        {/* Unmapped fields grouped by depth, dimmed */}
        {unmappedDepths.map(depth => {
          const depthFields = unmappedByDepth.get(depth)!
          const isAncestor = depth > 0
          const depthLabel = DEPTH_LABELS[depth] ?? `Ancestor (depth ${depth}) Fields`

          const rows = depthFields.map(field => {
            const displayPath = field.is_array_child
              ? '.' + field.path.split('[].').pop()
              : field.path
            return (
              <div
                key={field.path}
                className={`relative flex items-center gap-2 px-3 py-2 text-xs hover:bg-muted/30 opacity-60 ${
                  field.is_array_child ? 'pl-4 border-l-2 border-orange-300 dark:border-orange-500' : ''
                }`}
              >
                <span className="flex-1 font-mono truncate">{displayPath}</span>
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
            )
          })

          if (isAncestor) {
            return (
              <div key={depth} className="bg-blue-50 dark:bg-blue-950/20 border-l-2 border-blue-400 dark:border-blue-500">
                <div className="px-3 py-1 text-xs font-medium text-muted-foreground">{depthLabel}</div>
                {rows}
              </div>
            )
          }

          return <div key={depth}>{rows}</div>
        })}
      </div>
    </div>
  )
}
