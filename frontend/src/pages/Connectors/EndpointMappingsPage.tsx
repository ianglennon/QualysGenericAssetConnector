import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ROUTES } from '@/routes/constants'
import { ArrowLeft, Save, Trash2 } from 'lucide-react'
import { useConnector } from '@/hooks/queries/useConnectors'
import { useEndpoints } from '@/hooks/queries/useEndpoints'
import { useQualysSchema } from '@/hooks/queries/useQualysSchema'
import { useBatchReplaceEndpointMappings } from '@/hooks/queries/useEndpointMappings'
import { MappingCanvas, ConfirmClearDialog } from '@/components/mappings/MappingCanvas'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/hooks/use-toast'
import { canvasTypeToAPI } from '@/types/canvas'
import type { MappingEdgeData } from '@/types/canvas'
import type { FieldMappingCreate } from '@/types/api'
import type { Edge } from '@xyflow/react'

export function EndpointMappingsPage() {
  const { connectorId, endpointId } = useParams<{ connectorId: string; endpointId: string }>()
  const [canvasEdges, setCanvasEdges] = useState<Edge<MappingEdgeData>[]>([])
  const [confirmClearOpen, setConfirmClearOpen] = useState(false)
  const [clearKey, setClearKey] = useState(0)

  const { data: connector, isLoading: loadingConnector } = useConnector(connectorId)
  const { data: endpoints, isLoading: loadingEndpoints } = useEndpoints(connectorId)
  const { data: schemaData } = useQualysSchema()
  const batchReplace = useBatchReplaceEndpointMappings()
  const { toast } = useToast()

  const endpoint = endpoints?.find(e => e.id === endpointId)

  // Identity gate (MAP-03): save disabled when no identity attribute edge present
  const identityFields = new Set(
    schemaData?.fields.filter(f => f.is_identity).map(f => f.field) ?? []
  )
  const hasIdentityLinked = canvasEdges.some(
    e => e.targetHandle && identityFields.has(e.targetHandle)
  )
  const hasUnconfiguredWidget = canvasEdges.some(e => {
    const d = e.data as MappingEdgeData
    if (d.mappingType === 'static') return d.staticValue === undefined || d.staticValue === ''
    if (d.mappingType === 'conditional') return !d.conditions?.length
    return false
  })

  const saveDisabled =
    !connectorId ||
    !endpointId ||
    !hasIdentityLinked ||
    hasUnconfiguredWidget ||
    batchReplace.isPending

  const removeAllDisabled = canvasEdges.length === 0 || batchReplace.isPending

  function buildSavePayload(edges: Edge<MappingEdgeData>[]): FieldMappingCreate[] {
    return edges.map((e, i) => {
      const d = e.data!
      const base: FieldMappingCreate = {
        source_field: e.sourceHandle ?? '',
        target_field: e.targetHandle ?? '',
        mapping_type: canvasTypeToAPI(d.mappingType),
        order: i,
      }
      if (d.mappingType === 'static') {
        return { ...base, static_value: String(d.staticValue ?? '') }
      }
      if (d.mappingType === 'conditional') {
        return { ...base, conditions: d.conditions ?? [], fallback: d.fallback }
      }
      return base
    })
  }

  async function handleSave() {
    if (!connectorId || !endpointId) return
    const mappings = buildSavePayload(canvasEdges)
    try {
      await batchReplace.mutateAsync({ connectorId, endpointId, mappings })
      toast({
        title: 'Mappings saved',
        description: `${mappings.length} mapping(s) saved successfully.`,
      })
    } catch (err) {
      toast({
        title: 'Failed to save mappings',
        description: String(err),
        variant: 'destructive',
      })
    }
  }

  async function handleRemoveAll() {
    setConfirmClearOpen(false)
    if (!connectorId || !endpointId) return
    try {
      await batchReplace.mutateAsync({ connectorId, endpointId, mappings: [] })
      setClearKey(k => k + 1)
      toast({ title: 'All mappings removed' })
    } catch (err) {
      toast({
        title: 'Failed to remove mappings',
        description: String(err),
        variant: 'destructive',
      })
    }
  }

  const isLoading = loadingConnector || loadingEndpoints

  return (
    <div className="flex flex-col h-full">
      {/* Page header */}
      <div className="flex items-center justify-between px-6 py-4 border-b shrink-0">
        <div className="flex items-center gap-4">
          <Link
            to={ROUTES.connectorDetail(connectorId ?? '')}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Back to connector"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            {isLoading ? (
              <>
                <Skeleton className="h-7 w-48 mb-1" />
                <Skeleton className="h-4 w-64" />
              </>
            ) : (
              <>
                <h1 className="text-2xl font-bold tracking-tight">
                  {endpoint?.name ?? 'Endpoint'} — Field Mappings
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {connector?.name ?? 'Connector'} &rsaquo; {endpoint?.path?.startsWith('/') ? endpoint.path : `/${endpoint?.path ?? ''}`}
                </p>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={removeAllDisabled}
            onClick={() => setConfirmClearOpen(true)}
            title={canvasEdges.length === 0 ? 'No mappings to remove' : undefined}
          >
            <Trash2 className="w-4 h-4 mr-1" />
            Remove All
          </Button>
          <Button
            onClick={handleSave}
            disabled={saveDisabled}
            size="sm"
            title={!hasIdentityLinked ? 'Link at least one identity attribute (\u2605) to save' : undefined}
          >
            <Save className="w-4 h-4 mr-1" />
            Save Mappings
          </Button>
        </div>
      </div>

      {/* Canvas area */}
      <div className="flex-1 min-h-0">
        {connectorId && endpointId ? (
          <MappingCanvas
            key={clearKey}
            connectorId={connectorId}
            endpointId={endpointId}
            onEdgesSnapshot={setCanvasEdges}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            Missing connector or endpoint context.
          </div>
        )}
      </div>
      <ConfirmClearDialog
        open={confirmClearOpen}
        onConfirm={handleRemoveAll}
        onCancel={() => setConfirmClearOpen(false)}
      />
    </div>
  )
}
