import { useEffect, useCallback } from 'react'
import { useUpdateNodeInternals, useNodeId, Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import { Trash2, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { TemplateVariableHint } from './TemplateVariableHint'
import type { EndpointNodeData, FieldDiscoveryItem } from '@/types/canvas'

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
}

type EndpointNodeFullData = EndpointNodeData & EndpointNodeCallbacks

export function EndpointNode({ data, selected }: NodeProps & { data: EndpointNodeFullData }) {
  const nodeId = useNodeId() ?? 'endpoint-node'
  const updateNodeInternals = useUpdateNodeInternals()

  // Re-register handle positions when fields change
  useEffect(() => {
    if (data.fields.length > 0) {
      requestAnimationFrame(() => updateNodeInternals(nodeId))
    }
  }, [data.fields, nodeId, updateNodeInternals])

  const handleScroll = useCallback(() => {
    updateNodeInternals(nodeId)
  }, [nodeId, updateNodeInternals])

  const canDiscover = !data.isDiscovering && data.name.trim() !== '' && data.path.trim() !== ''

  return (
    <div
      className={`flex flex-col bg-card border rounded-lg shadow-sm min-w-[280px] max-h-[500px] ${
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

      {/* Field list */}
      {data.fields.length > 0 && (
        <div
          className="nowheel overflow-y-auto overflow-x-hidden flex-1 border-t"
          onScroll={handleScroll}
        >
          {data.fields.map((field: FieldDiscoveryItem) => (
            <div
              key={field.path}
              className="relative flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted/30"
            >
              <span
                className={`px-1 rounded text-[10px] font-medium ${typeBadgeClass(field.type)}`}
              >
                {field.type}
              </span>
              <span className="flex-1 font-mono truncate text-sm">{field.path}</span>
              <Handle
                type="source"
                position={Position.Right}
                id={field.path}
                style={SOURCE_HANDLE_STYLE}
              />
            </div>
          ))}
        </div>
      )}

      {/* Footer: Max Concurrency */}
      <div className="flex items-center gap-2 px-3 py-2 border-t">
        <label className="text-xs text-muted-foreground whitespace-nowrap">Max Concurrency</label>
        <Input
          type="number"
          className="h-6 w-16 text-xs border-none bg-transparent shadow-none focus-visible:ring-0 p-0 text-right"
          min={1}
          placeholder="5"
          value={data.maxConcurrency}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10)
            if (!isNaN(val) && val >= 1) {
              data.onMaxConcurrencyChange?.(val)
            }
          }}
        />
      </div>
    </div>
  )
}
