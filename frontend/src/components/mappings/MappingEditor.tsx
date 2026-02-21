import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Save } from 'lucide-react'
import { SourceFieldList } from './SourceFieldList'
import { TransformationPanel } from './TransformationPanel'
import { TargetFieldList } from './TargetFieldList'
import { PreviewPanel } from './PreviewPanel'
import {
  useMappings,
  useCreateMapping,
  useDeleteMapping,
} from '@/hooks/queries/useMappings'
import type { FieldMappingCreate } from '@/types/api'

const QUALYS_FIELDS = ['name', 'netbiosName', 'address', 'domain', 'fqdn', 'os', 'manufacturer']

interface MappingEditorProps {
  connectorId: string
}

export const MappingEditor = ({ connectorId }: MappingEditorProps) => {
  const [sourceFields, setSourceFields] = useState<string[]>([])
  const [selectedSourceField, setSelectedSourceField] = useState<string | null>(null)
  const [selectedTargetField, setSelectedTargetField] = useState<string | null>(null)
  const [sampleData, _setSampleData] = useState<any>(null)

  const { data: mappings = [], isLoading: _isLoading } = useMappings(connectorId)
  const createMutation = useCreateMapping()
  const deleteMutation = useDeleteMapping()
  const { toast } = useToast()

  const handleFieldsLoaded = (fields: string[]) => {
    setSourceFields(fields)
  }

  const handleAddMapping = async (mapping: FieldMappingCreate) => {
    try {
      await createMutation.mutateAsync({
        connectorId,
        mapping: { ...mapping, connector_id: connectorId },
      })
      toast({
        title: 'Mapping added',
        description: `Successfully mapped to ${mapping.target_field}`,
      })
    } catch (error: any) {
      toast({
        title: 'Failed to add mapping',
        description: error.response?.data?.detail?.message || 'An error occurred',
        variant: 'destructive',
      })
    }
  }

  const handleDeleteMapping = async (mappingId: string) => {
    try {
      await deleteMutation.mutateAsync({ connectorId, mappingId })
      toast({
        title: 'Mapping deleted',
        description: 'Successfully removed mapping',
      })
    } catch (error: any) {
      toast({
        title: 'Failed to delete mapping',
        description: error.response?.data?.detail?.message || 'An error occurred',
        variant: 'destructive',
      })
    }
  }

  // Check validation
  const requiredFields = ['name', 'netbiosName', 'address']
  const mappedTargets = new Set(mappings.map((m) => m.target_field))
  const hasRequiredField = requiredFields.some((field) => mappedTargets.has(field))
  const isValid = mappings.length > 0 && hasRequiredField

  return (
    <div className="h-full flex flex-col">
      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Source Fields - Left Panel */}
        <div className="flex flex-col min-h-0">
          <SourceFieldList
            connectorId={connectorId}
            onFieldsLoaded={handleFieldsLoaded}
            selectedField={selectedSourceField}
            onFieldSelect={setSelectedSourceField}
          />
        </div>

        {/* Transformations - Center Panel */}
        <div className="flex flex-col min-h-0">
          <TransformationPanel
            mappings={mappings}
            sourceFields={sourceFields}
            targetFields={QUALYS_FIELDS}
            onAddMapping={handleAddMapping}
            onDeleteMapping={handleDeleteMapping}
          />
        </div>

        {/* Target Fields - Right Panel */}
        <div className="flex flex-col min-h-0">
          <TargetFieldList
            mappedFields={mappedTargets}
            selectedField={selectedTargetField}
            onFieldSelect={setSelectedTargetField}
          />
        </div>
      </div>

      {/* Preview Panel - Bottom */}
      <PreviewPanel
        connectorId={connectorId}
        mappings={mappings}
        sampleData={sampleData}
      />

      {/* Save Button */}
      <div className="flex justify-end pt-4">
        <Button
          disabled={!isValid || createMutation.isPending || deleteMutation.isPending}
          onClick={() => {
            toast({
              title: 'Mappings saved',
              description: 'All mappings are already persisted',
            })
          }}
        >
          {createMutation.isPending || deleteMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          {isValid ? 'Mappings Valid' : 'Invalid - Add Required Fields'}
        </Button>
      </div>
    </div>
  )
}
