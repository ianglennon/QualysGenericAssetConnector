import { useState } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { MappingCanvas, ConfirmClearDialog } from '@/components/mappings/MappingCanvas'
import { useConnectors } from '@/hooks/queries/useConnectors'
import { useQualysSchema } from '@/hooks/queries/useQualysSchema'
import { useBatchReplaceMappings } from '@/hooks/queries/useMappings'
import { useToast } from '@/hooks/use-toast'
import { canvasTypeToAPI } from '@/types/canvas'
import type { MappingEdgeData } from '@/types/canvas'
import type { FieldMappingCreate } from '@/types/api'
import type { Edge } from '@xyflow/react'
import { Save, Trash2 } from 'lucide-react'

export default function Mappings() {
  const [selectedConnectorId, setSelectedConnectorId] = useState<string>('')
  const [canvasEdges, setCanvasEdges] = useState<Edge<MappingEdgeData>[]>([])
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [clearKey, setClearKey] = useState(0)

  const { data: connectors, isLoading } = useConnectors()
  const { data: schemaData } = useQualysSchema()
  const batchReplace = useBatchReplaceMappings()
  const { toast } = useToast()

  // Identity gate
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
  const saveDisabled = !selectedConnectorId || !hasIdentityLinked || hasUnconfiguredWidget || batchReplace.isPending

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
    const mappings = buildSavePayload(canvasEdges)
    try {
      await batchReplace.mutateAsync({ connectorId: selectedConnectorId, mappings })
      toast({ title: 'Mappings saved', description: `${mappings.length} mapping(s) saved successfully.` })
    } catch (err) {
      toast({ title: 'Failed to save mappings', description: String(err), variant: 'destructive' })
    }
  }

  async function handleRemoveAll() {
    setClearDialogOpen(false)
    try {
      await batchReplace.mutateAsync({ connectorId: selectedConnectorId, mappings: [] })
      setCanvasEdges([])
      setClearKey(k => k + 1)
      toast({ title: 'Mappings removed', description: 'All mappings have been removed.' })
    } catch (err) {
      toast({ title: 'Failed to remove mappings', description: String(err), variant: 'destructive' })
    }
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Field Mappings</h1>
          <p className="text-muted-foreground mt-2">
            Configure how source fields are mapped to Qualys CSAM asset fields
          </p>
        </div>
        {selectedConnectorId && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setClearDialogOpen(true)}
              disabled={batchReplace.isPending || canvasEdges.length === 0}
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Remove all
            </Button>
            <Button
              onClick={handleSave}
              disabled={saveDisabled}
              size="sm"
              title={!hasIdentityLinked ? 'Link at least one identity attribute (★) to save' : undefined}
            >
              <Save className="w-4 h-4 mr-1" />
              Save Mappings
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Select Connector</CardTitle>
          <CardDescription>
            Choose a connector to configure its field mappings
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (
            <Select value={selectedConnectorId} onValueChange={setSelectedConnectorId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a connector..." />
              </SelectTrigger>
              <SelectContent>
                {connectors?.map((connector) => (
                  <SelectItem key={connector.id} value={connector.id}>
                    {connector.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>

      {selectedConnectorId && (
        <Card>
          <CardHeader>
            <CardTitle>Field Mapping Canvas</CardTitle>
            <CardDescription>
              Drag from source fields on the left to Qualys target fields on the right to create mappings
            </CardDescription>
          </CardHeader>
          <CardContent className="h-[600px]">
            <MappingCanvas
              key={clearKey}
              connectorId={selectedConnectorId}
              endpointId=""
              onEdgesSnapshot={setCanvasEdges}
            />
          </CardContent>
        </Card>
      )}

      <ConfirmClearDialog
        open={clearDialogOpen}
        onConfirm={handleRemoveAll}
        onCancel={() => setClearDialogOpen(false)}
      />
    </div>
  )
}
