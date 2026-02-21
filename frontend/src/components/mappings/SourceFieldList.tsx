import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useLoadSourceFields } from '@/hooks/queries/useMappings'
import { Upload, Loader2 } from 'lucide-react'

interface SourceFieldListProps {
  connectorId: string | undefined
  onFieldsLoaded: (fields: string[]) => void
  selectedField: string | null
  onFieldSelect: (field: string) => void
}

export const SourceFieldList = ({
  connectorId,
  onFieldsLoaded,
  selectedField,
  onFieldSelect,
}: SourceFieldListProps) => {
  const [sourceFields, setSourceFields] = useState<string[]>([])
  const loadMutation = useLoadSourceFields()

  const handleLoadFields = async () => {
    if (!connectorId) return

    try {
      const sampleData = await loadMutation.mutateAsync(connectorId)
      const fields = extractFields(sampleData)
      setSourceFields(fields)
      onFieldsLoaded(fields)
    } catch (error) {
      console.error('Failed to load source fields:', error)
    }
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const json = JSON.parse(e.target?.result as string)
        const fields = extractFields(json)
        setSourceFields(fields)
        onFieldsLoaded(fields)
      } catch (error) {
        console.error('Failed to parse JSON:', error)
      }
    }
    reader.readAsText(file)
  }

  const extractFields = (obj: any, prefix = ''): string[] => {
    if (!obj || typeof obj !== 'object') return []

    const fields: string[] = []
    for (const key in obj) {
      const fullKey = prefix ? `${prefix}.${key}` : key
      const value = obj[key]

      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        // Nested object - recurse
        fields.push(...extractFields(value, fullKey))
      } else {
        // Primitive or array - add field
        fields.push(fullKey)
      }
    }
    return fields
  }

  const getFieldType = (field: string): string => {
    // Simple type detection based on field name patterns
    if (field.includes('id') || field.includes('Id')) return 'string'
    if (field.includes('count') || field.includes('Count')) return 'number'
    if (field.includes('is') || field.includes('enabled')) return 'boolean'
    if (field.includes('list') || field.includes('items')) return 'array'
    return 'string'
  }

  return (
    <div className="h-full flex flex-col border rounded-lg p-4 bg-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Source Fields</h3>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleLoadFields}
            disabled={!connectorId || loadMutation.isPending}
          >
            {loadMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              'Load Source Fields'
            )}
          </Button>
          <label>
            <Button variant="outline" size="sm" asChild>
              <span>
                <Upload className="h-4 w-4 mr-2" />
                Upload JSON
              </span>
            </Button>
            <input
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleFileUpload}
            />
          </label>
        </div>
      </div>

      {sourceFields.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <p className="text-sm text-center">
            Click "Load Source Fields" to fetch<br />sample data from connector
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-auto space-y-1">
          {sourceFields.map((field) => (
            <button
              key={field}
              onClick={() => onFieldSelect(field)}
              className={`
                w-full text-left px-3 py-2 rounded-md text-sm
                hover:bg-accent transition-colors
                ${selectedField === field ? 'bg-accent font-medium' : ''}
              `}
            >
              <div className="flex items-center justify-between">
                <span>{field}</span>
                <span className="text-xs text-muted-foreground">
                  {getFieldType(field)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
