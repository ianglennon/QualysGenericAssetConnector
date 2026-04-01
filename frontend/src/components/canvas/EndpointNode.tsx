import { useState, useEffect, useCallback } from 'react'
import { useUpdateNodeInternals, useNodeId, useReactFlow, Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import { Trash2, Loader2, Filter } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TemplateVariableHint } from './TemplateVariableHint'
import { ExclusionRulesDialog } from './ExclusionRulesDialog'
import type { EndpointNodeData, FieldDiscoveryItem, ExclusionRule } from '@/types/canvas'
import { typeBadgeClass } from '@/lib/field-type-colors'

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

const TARGET_HANDLE_STYLE: React.CSSProperties = {
  left: 0,
  top: 16,
  width: 12,
  height: 12,
  background: 'hsl(var(--primary) / 0.6)',
  border: '2px solid hsl(var(--background))',
  borderRadius: '50%',
  zIndex: 10,
}

/** Callback props injected by ChainCanvas (Plan 03) when constructing node data */
interface EndpointNodeCallbacks {
  onNameChange?: (name: string) => void
  onPathChange?: (path: string) => void
  onDiscoverFields?: () => void
  onDelete?: () => void
  onMaxConcurrencyChange?: (value: number) => void
  onExclusionRulesChange?: (rules: ExclusionRule[]) => void
}

type EndpointNodeFullData = EndpointNodeData & EndpointNodeCallbacks

export function EndpointNode({ data, selected }: NodeProps & { data: EndpointNodeFullData }) {
  const nodeId = useNodeId() ?? 'endpoint-node'
  const updateNodeInternals = useUpdateNodeInternals()
  const { setNodes } = useReactFlow()
  const [filterDialogOpen, setFilterDialogOpen] = useState(false)

  // Re-register handle positions when fields change
  useEffect(() => {
    if (data.fields.length > 0) {
      requestAnimationFrame(() => updateNodeInternals(nodeId))
    }
  }, [data.fields, data.linkedSourceFields, data.linkedFieldOrder, nodeId, updateNodeInternals])

  const handleScroll = useCallback(() => {
    updateNodeInternals(nodeId)
  }, [nodeId, updateNodeInternals])

  const canDiscover = !data.isDiscovering && data.name.trim() !== '' && data.path.trim() !== ''

  // Mapped fields sorted by edge index
  const linked = data.linkedSourceFields ?? new Set<string>()
  const order = data.linkedFieldOrder ?? new Map<string, number>()

  const mapped = data.fields
    .filter(f => linked.has(f.path))
    .sort((a, b) => {
      const posA = order.get(a.path) ?? Infinity
      const posB = order.get(b.path) ?? Infinity
      if (posA !== posB) return posA - posB
      return a.path.localeCompare(b.path)
    })

  const unmapped = data.fields
    .filter(f => !linked.has(f.path))
    .sort((a, b) => a.path.localeCompare(b.path))

  function handleResizeStart(e: React.PointerEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    const target = e.currentTarget
    target.setPointerCapture(e.pointerId)
    const startY = e.clientY
    const nodeEl = target.closest('.react-flow__node') as HTMLElement | null
    const startH = nodeEl ? nodeEl.offsetHeight : 500

    const onMove = (ev: PointerEvent) => {
      const delta = ev.clientY - startY
      const newH = Math.max(200, Math.min(800, startH + delta))
      setNodes(nds => nds.map(n => {
        if (n.id !== nodeId) return n
        return { ...n, style: { ...n.style, height: newH } }
      }))
      requestAnimationFrame(() => updateNodeInternals(nodeId))
    }

    const onUp = () => {
      target.removeEventListener('pointermove', onMove)
      target.removeEventListener('pointerup', onUp)
    }

    target.addEventListener('pointermove', onMove)
    target.addEventListener('pointerup', onUp)
  }

  function renderField(field: FieldDiscoveryItem, isMapped: boolean) {
    const isArrayChild = field.is_array_child === true
    const isArrayParent = field.is_array_parent === true
    const displayPath = isArrayChild
      ? '.' + field.path.split('[].').pop()
      : field.path

    return (
      <div
        key={field.path}
        className={`relative flex items-center gap-2 px-3 py-1.5 text-xs ${
          isMapped
            ? `border-l-2 ${isArrayChild ? 'pl-4 border-orange-300 dark:border-orange-500' : 'border-primary/40'} bg-primary/5`
            : `hover:bg-muted/30 opacity-60 ${isArrayChild ? 'pl-4 border-l-2 border-orange-300 dark:border-orange-500' : ''}`
        }`}
      >
        <span
          className={`px-1 rounded text-[10px] font-medium ${typeBadgeClass(isArrayParent ? 'array' : field.type)}`}
        >
          {isArrayParent ? 'array' : field.type}
        </span>
        <span className="flex-1 font-mono truncate text-sm">{displayPath}</span>
        <Handle
          type="source"
          position={Position.Right}
          id={field.path}
          isConnectable={!isMapped}
          style={SOURCE_HANDLE_STYLE}
        />
      </div>
    )
  }

  return (
    <div
      className={`flex flex-col bg-card border rounded-lg shadow-sm min-w-[280px] h-full overflow-hidden ${
        selected ? 'ring-2 ring-primary' : ''
      }`}
    >
      {/* Left-side target handle for receiving chain connections from parent */}
      <Handle
        type="target"
        position={Position.Left}
        id={`${nodeId}-target`}
        style={TARGET_HANDLE_STYLE}
      />

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/40">
        <Input
          className="flex-1 h-7 text-base font-semibold border-none bg-transparent shadow-none focus-visible:ring-0 p-0"
          placeholder="Endpoint name"
          value={data.name}
          onChange={(e) => data.onNameChange?.(e.target.value)}
        />
        <button
          className="p-1 text-muted-foreground hover:text-destructive rounded"
          aria-label="Delete endpoint"
          onClick={() => data.onDelete?.()}
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Path section */}
      <div className="px-3 py-2">
        <Input
          className="h-7 text-sm font-normal border-none bg-transparent shadow-none focus-visible:ring-0 p-0"
          placeholder="/api/path"
          value={data.path}
          onChange={(e) => data.onPathChange?.(e.target.value)}
        />
        <TemplateVariableHint path={data.path} />
      </div>

      {/* Discover Fields button */}
      <div className="px-3 pb-2">
        <Button
          variant="outline"
          size="sm"
          disabled={!canDiscover}
          onClick={() => data.onDiscoverFields?.()}
          className="w-full"
        >
          {data.isDiscovering ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin" />
              Discovering...
            </>
          ) : (
            'Discover Fields'
          )}
        </Button>
      </div>

      {/* Discovery error */}
      {data.discoveryError && (
        <div className="px-3 pb-2">
          <p className="text-xs text-destructive">{data.discoveryError}</p>
        </div>
      )}

      {/* Filter section (D-07, D-09) */}
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          className="flex items-center justify-center h-8 w-8 min-h-[48px] min-w-[48px] rounded text-muted-foreground hover:text-foreground hover:bg-muted"
          aria-label="Edit exclusion rules"
          onClick={() => setFilterDialogOpen(true)}
        >
          <Filter className="h-4 w-4" />
        </button>
        {(data.exclusionRules?.length ?? 0) > 0 && (
          <Badge variant="secondary">
            {data.exclusionRules.length} {data.exclusionRules.length === 1 ? 'filter' : 'filters'}
          </Badge>
        )}
      </div>

      <ExclusionRulesDialog
        open={filterDialogOpen}
        onOpenChange={setFilterDialogOpen}
        rules={data.exclusionRules ?? []}
        onSave={(rules) => data.onExclusionRulesChange?.(rules)}
        fieldSuggestions={data.fields.map((f: FieldDiscoveryItem) => f.path)}
      />

      {/* Frozen section: mapped fields pinned at top */}
      {data.fields.length > 0 && (
        <div
          className={`nowheel overflow-y-auto overflow-x-hidden shrink-0 border-t ${
            mapped.length > 0
              ? 'shadow-[0_2px_4px_-1px_rgba(0,0,0,0.1)] dark:shadow-[0_2px_4px_-1px_rgba(255,255,255,0.06)]'
              : ''
          }`}
          style={{ pointerEvents: 'auto', maxHeight: 'calc(40% - 24px)' }}
          onScroll={handleScroll}
        >
          {mapped.map(field => renderField(field, true))}
        </div>
      )}

      {/* Divider between frozen and scrollable sections */}
      {mapped.length > 0 && unmapped.length > 0 && (
        <div className="border-t border-border my-1" />
      )}

      {/* Scrollable section: unmapped fields */}
      {data.fields.length > 0 && (
        <div
          className="nowheel overflow-y-auto overflow-x-hidden flex-1 min-h-0"
          style={{ pointerEvents: 'auto' }}
          onScroll={handleScroll}
        >
          {unmapped.map(field => renderField(field, false))}
        </div>
      )}

      {/* Footer: Max Concurrency */}
      <div className="flex items-center gap-2 px-3 py-2 border-t">
        <label className="text-xs text-muted-foreground whitespace-nowrap">Max Concurrency</label>
        <div className="flex items-center gap-1">
          <button
            className="h-5 w-5 flex items-center justify-center rounded text-xs text-muted-foreground hover:bg-muted"
            onClick={() => {
              const val = (data.maxConcurrency ?? 5) - 1
              if (val >= 1) data.onMaxConcurrencyChange?.(val)
            }}
          >
            −
          </button>
          <Input
            type="text"
            inputMode="numeric"
            className="h-6 w-10 text-xs border-none bg-transparent shadow-none focus-visible:ring-0 p-0 text-center [appearance:textfield]"
            placeholder="5"
            value={data.maxConcurrency}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10)
              if (!isNaN(val) && val >= 1) {
                data.onMaxConcurrencyChange?.(val)
              }
            }}
          />
          <button
            className="h-5 w-5 flex items-center justify-center rounded text-xs text-muted-foreground hover:bg-muted"
            onClick={() => data.onMaxConcurrencyChange?.((data.maxConcurrency ?? 5) + 1)}
          >
            +
          </button>
        </div>
      </div>

      {/* Resize handle */}
      <div
        className="h-3 cursor-row-resize flex items-center justify-center shrink-0"
        onPointerDown={handleResizeStart}
      >
        <div className="w-8 h-0.5 rounded-full bg-muted-foreground/40" />
      </div>
    </div>
  )
}
