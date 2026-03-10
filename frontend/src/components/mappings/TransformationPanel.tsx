import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, Trash2, GripVertical } from 'lucide-react'
import type { FieldMapping, FieldMappingCreate, MappingType, MappingTypeAPI } from '@/types/api'
import { canvasTypeToAPI } from '@/types/canvas'

interface TransformationPanelProps {
  mappings: FieldMapping[]
  sourceFields: string[]
  targetFields: string[]
  onAddMapping: (mapping: FieldMappingCreate) => void
  onDeleteMapping: (mappingId: string) => void
}

export const TransformationPanel = ({
  mappings,
  sourceFields,
  targetFields,
  onAddMapping,
  onDeleteMapping,
}: TransformationPanelProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [sourceField, setSourceField] = useState('')
  const [targetField, setTargetField] = useState('')
  const [mappingType, setMappingType] = useState<MappingType>('direct')
  const [staticValue, setStaticValue] = useState('')
  const [conditionField, setConditionField] = useState('')
  const [conditionOperator, setConditionOperator] = useState('equals')
  const [conditionValue, setConditionValue] = useState('')
  const [conditionThenValue, setConditionThenValue] = useState('')
  const [conditionElseValue, setConditionElseValue] = useState('')

  const handleSubmit = () => {
    const newMapping: FieldMappingCreate = {
      connector_id: '', // Will be set by parent
      source_field: mappingType === 'direct' ? sourceField : undefined,
      target_field: targetField,
      mapping_type: canvasTypeToAPI(mappingType),
      static_value: mappingType === 'static' ? staticValue : undefined,
      conditions:
        mappingType === 'conditional'
          ? [
              {
                operator: conditionOperator as 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'ends_with' | 'regex' | 'in_list',
                source_field: conditionField,
                target_value: conditionValue,
                value: conditionThenValue,
              },
            ]
          : undefined,
      fallback: mappingType === 'conditional' && conditionElseValue ? conditionElseValue : undefined,
      order: mappings.length,
    }

    onAddMapping(newMapping)
    setIsOpen(false)
    resetForm()
  }

  const resetForm = () => {
    setSourceField('')
    setTargetField('')
    setMappingType('direct')
    setStaticValue('')
    setConditionField('')
    setConditionOperator('equals')
    setConditionValue('')
    setConditionThenValue('')
    setConditionElseValue('')
  }

  const getMappingTypeLabel = (type: MappingTypeAPI): string => {
    switch (type) {
      case 'direct_copy':
        return 'Direct Copy'
      case 'static_default':
        return 'Static Value'
      case 'conditional':
        return 'Conditional'
      default:
        return type
    }
  }

  return (
    <div className="h-full flex flex-col border rounded-lg p-4 bg-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Transformations</h3>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-2" />
              Add Mapping
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Add Field Mapping</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Mapping Type</Label>
                <Select value={mappingType} onValueChange={(v) => setMappingType(v as MappingType)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="direct">Direct Copy</SelectItem>
                    <SelectItem value="static">Static Value</SelectItem>
                    <SelectItem value="conditional">Conditional</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {mappingType === 'direct' && (
                <div className="space-y-2">
                  <Label>Source Field</Label>
                  <Select value={sourceField} onValueChange={setSourceField}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select source field" />
                    </SelectTrigger>
                    <SelectContent>
                      {sourceFields.map((field) => (
                        <SelectItem key={field} value={field}>
                          {field}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {mappingType === 'static' && (
                <div className="space-y-2">
                  <Label>Static Value</Label>
                  <Input
                    value={staticValue}
                    onChange={(e) => setStaticValue(e.target.value)}
                    placeholder="Enter static value"
                  />
                </div>
              )}

              {mappingType === 'conditional' && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label>Source Field to Check</Label>
                    <Select value={conditionField} onValueChange={setConditionField}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select field" />
                      </SelectTrigger>
                      <SelectContent>
                        {sourceFields.map((field) => (
                          <SelectItem key={field} value={field}>
                            {field}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Operator</Label>
                    <Select value={conditionOperator} onValueChange={setConditionOperator}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="equals">Equals</SelectItem>
                        <SelectItem value="not_equals">Not Equals</SelectItem>
                        <SelectItem value="contains">Contains</SelectItem>
                        <SelectItem value="regex">Regex Match</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Compare Value</Label>
                    <Input
                      value={conditionValue}
                      onChange={(e) => setConditionValue(e.target.value)}
                      placeholder="Value to compare"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Then Value (if true)</Label>
                    <Input
                      value={conditionThenValue}
                      onChange={(e) => setConditionThenValue(e.target.value)}
                      placeholder="Value when condition matches"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Else Value (if false, optional)</Label>
                    <Input
                      value={conditionElseValue}
                      onChange={(e) => setConditionElseValue(e.target.value)}
                      placeholder="Value when condition doesn't match"
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label>Target Field</Label>
                <Select value={targetField} onValueChange={setTargetField}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select target field" />
                  </SelectTrigger>
                  <SelectContent>
                    {targetFields.map((field) => (
                      <SelectItem key={field} value={field}>
                        {field}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setIsOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={
                    !targetField ||
                    (mappingType === 'direct' && !sourceField) ||
                    (mappingType === 'static' && !staticValue) ||
                    (mappingType === 'conditional' &&
                      (!conditionField || !conditionValue || !conditionThenValue))
                  }
                >
                  Add Mapping
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {mappings.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <p className="text-sm text-center">
            No mappings configured.<br />Click "Add Mapping" to create one.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-auto space-y-2">
          {mappings.map((mapping) => (
            <div
              key={mapping.id}
              className="flex items-center gap-2 p-3 border rounded-md bg-background hover:bg-accent/50 transition-colors"
            >
              <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium truncate">
                    {mapping.source_field || mapping.static_value || 'Conditional'}
                  </span>
                  <span className="text-muted-foreground">→</span>
                  <Badge variant="secondary" className="text-xs">
                    {getMappingTypeLabel(mapping.mapping_type)}
                  </Badge>
                  <span className="text-muted-foreground">→</span>
                  <span className="text-sm font-medium">{mapping.target_field}</span>
                </div>
                {mapping.conditions && mapping.conditions.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    {mapping.conditions[0].source_field} {mapping.conditions[0].operator}{' '}
                    {mapping.conditions[0].target_value}
                  </div>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDeleteMapping(mapping.id)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
