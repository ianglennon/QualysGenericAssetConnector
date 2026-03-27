import { useState, useCallback, useRef } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
} from '@xyflow/react'
import type { MappingEdgeData, MappingTypeUI, StaticValueType, CanvasConditionRule, CollectConfig } from '@/types/canvas'
import { StaticValueEditor } from './StaticValueEditor'
import { ConditionalEditor } from './ConditionalEditor'
import { CollectEditor } from './CollectEditor'

export type MappingEdgeType = Edge<MappingEdgeData, 'mapping'>

const CYCLE: MappingTypeUI[] = ['direct', 'static', 'conditional', 'collect']
const CUSTOM_ATTR_CYCLE: MappingTypeUI[] = ['direct', 'static', 'conditional']

export function MappingEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps<MappingEdgeType>) {
  const { deleteElements, setEdges, getEdge, getNodes } = useReactFlow()
  const [hovered, setHovered] = useState(false)
  const [editorOpen, setEditorOpen] = useState<'static' | 'conditional' | 'collect' | null>(null)
  const badgeRef = useRef<HTMLSpanElement>(null)

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const mappingType = (data?.mappingType ?? 'direct') as MappingTypeUI

  const isConfigured =
    mappingType === 'direct' ||
    (mappingType === 'static' && data?.staticValue !== undefined && data?.staticValue !== '') ||
    (mappingType === 'conditional' && Array.isArray(data?.conditions) && (data.conditions as CanvasConditionRule[]).length > 0) ||
    (mappingType === 'collect' && !!(data?.collectConfig as CollectConfig | undefined)?.array_path)

  const cycleType = useCallback(() => {
    const current = (data?.mappingType ?? 'direct') as MappingTypeUI
    const edge = getEdge(id)
    const isCustomAttr = edge?.targetHandle?.startsWith('customAttribute.')
    const cycle = isCustomAttr ? CUSTOM_ATTR_CYCLE : CYCLE
    const next = cycle[(cycle.indexOf(current) + 1) % cycle.length]

    // Pre-fill collectConfig from source field metadata when cycling TO collect
    let collectConfig: CollectConfig | undefined
    if (next === 'collect' && edge?.sourceHandle) {
      const sourceNode = getNodes().find(n => n.id === edge.source)
      const fields = (sourceNode?.data as any)?.fields as { path: string; is_array_child?: boolean; parent_array_path?: string; is_array_parent?: boolean }[] | undefined
      const fieldMeta = fields?.find(f => f.path === edge.sourceHandle)
      if (fieldMeta?.is_array_child && fieldMeta.parent_array_path) {
        collectConfig = {
          array_path: fieldMeta.parent_array_path,
          extract_field: fieldMeta.path.split('[].').pop() || '',
        }
      } else if (fieldMeta?.is_array_parent) {
        collectConfig = {
          array_path: fieldMeta.path.replace('[]', ''),
        }
      }
    }

    setEdges((eds) =>
      eds.map((e) =>
        e.id === id
          ? { ...e, data: { ...e.data, mappingType: next, staticValue: undefined, conditions: [], fallback: undefined, collectConfig } }
          : e
      )
    )
  }, [id, data?.mappingType, setEdges, getEdge, getNodes])

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      if (mappingType !== 'direct') {
        setEditorOpen(mappingType as 'static' | 'conditional' | 'collect')
      }
    },
    [mappingType]
  )

  // Get sourceHandle for locking in editors
  const sourceField = getEdge(id)?.sourceHandle ?? ''

  const badgeClassName =
    `px-2 py-0.5 text-xs rounded-full border font-medium cursor-pointer select-none ` +
    (mappingType === 'collect' && isConfigured
      ? 'bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-700 font-semibold'
      : isConfigured && mappingType !== 'direct'
        ? 'bg-primary/10 text-primary border-primary/30 font-semibold'
        : 'bg-muted text-muted-foreground border-border')

  const badgeLabel = `${mappingType}${isConfigured && mappingType !== 'direct' ? ' ✓' : ''}`

  // StaticValueEditor save handler (called from MappingEdge — inside ReactFlow tree)
  function handleStaticSave(value: string | number | boolean, valueType: StaticValueType) {
    setEdges((eds) =>
      eds.map((e) =>
        e.id === id
          ? { ...e, data: { ...e.data, staticValue: value, valueType } }
          : e
      )
    )
    setEditorOpen(null)
  }

  // ConditionalEditor save handler
  function handleConditionalSave(conditions: CanvasConditionRule[], fallback: string | undefined) {
    setEdges((eds) =>
      eds.map((e) =>
        e.id === id
          ? { ...e, data: { ...e.data, conditions, fallback } }
          : e
      )
    )
    setEditorOpen(null)
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{ strokeWidth: hovered ? 2 : 1.5, stroke: 'hsl(var(--primary))' }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className="nodrag nopan flex items-center gap-1"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {/* Type badge — left-click cycles, right-click opens editor */}
          <span
            ref={badgeRef}
            className={badgeClassName}
            onClick={cycleType}
            onContextMenu={handleContextMenu}
          >
            {badgeLabel}
          </span>

          {/* × button — only visible on hover */}
          {hovered && (
            <button
              className="w-4 h-4 flex items-center justify-center rounded-full bg-destructive/10 hover:bg-destructive/20 text-destructive text-xs leading-none"
              onClick={() => deleteElements({ edges: [{ id }] })}
              aria-label="Remove mapping"
            >
              ×
            </button>
          )}
        </div>
      </EdgeLabelRenderer>

      {/* StaticValueEditor — anchored to badge */}
      {editorOpen === 'static' && (
        <StaticValueEditor
          open={editorOpen === 'static'}
          onClose={() => setEditorOpen(null)}
          anchorRef={badgeRef}
          sourceField={sourceField}
          initialValue={data?.staticValue as string | number | boolean | undefined}
          initialType={data?.valueType as StaticValueType | undefined}
          onSave={handleStaticSave}
          onCancel={() => setEditorOpen(null)}
        />
      )}

      {/* ConditionalEditor */}
      {editorOpen === 'conditional' && (
        <ConditionalEditor
          open={editorOpen === 'conditional'}
          sourceField={sourceField}
          initialConditions={(data?.conditions as CanvasConditionRule[]) ?? []}
          initialFallback={data?.fallback as string | undefined}
          onSave={handleConditionalSave}
          onCancel={() => setEditorOpen(null)}
        />
      )}

      {/* CollectEditor */}
      {editorOpen === 'collect' && (
        <CollectEditor
          open={true}
          initialConfig={(data?.collectConfig as CollectConfig | undefined) || { array_path: '' }}
          onSave={(config) => {
            setEdges((eds) =>
              eds.map((e) =>
                e.id === id
                  ? { ...e, data: { ...e.data, collectConfig: config } }
                  : e
              )
            )
            setEditorOpen(null)
          }}
          onCancel={() => setEditorOpen(null)}
        />
      )}
    </>
  )
}
