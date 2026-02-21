import { Badge } from '@/components/ui/badge'
import { Check } from 'lucide-react'

interface TargetField {
  name: string
  description: string
  required: boolean
}

const QUALYS_CSAM_FIELDS: TargetField[] = [
  { name: 'name', description: 'Asset name', required: true },
  { name: 'netbiosName', description: 'NetBIOS name', required: true },
  { name: 'address', description: 'IP address', required: true },
  { name: 'domain', description: 'Domain name', required: false },
  { name: 'fqdn', description: 'Fully qualified domain name', required: false },
  { name: 'os', description: 'Operating system', required: false },
  { name: 'manufacturer', description: 'Manufacturer', required: false },
]

interface TargetFieldListProps {
  mappedFields: Set<string>
  selectedField: string | null
  onFieldSelect: (field: string) => void
}

export const TargetFieldList = ({
  mappedFields,
  selectedField,
  onFieldSelect,
}: TargetFieldListProps) => {
  return (
    <div className="h-full flex flex-col border rounded-lg p-4 bg-card">
      <div className="mb-4">
        <h3 className="text-lg font-semibold">Qualys CSAM Fields</h3>
        <p className="text-sm text-muted-foreground mt-1">
          At least one required field must be mapped
        </p>
      </div>

      <div className="flex-1 overflow-auto space-y-1">
        {QUALYS_CSAM_FIELDS.map((field) => (
          <button
            key={field.name}
            onClick={() => onFieldSelect(field.name)}
            className={`
              w-full text-left px-3 py-2 rounded-md text-sm
              hover:bg-accent transition-colors
              ${selectedField === field.name ? 'bg-accent font-medium' : ''}
            `}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span>{field.name}</span>
                  {field.required && (
                    <Badge variant="outline" className="text-xs">
                      Required
                    </Badge>
                  )}
                  {mappedFields.has(field.name) && (
                    <Check className="h-4 w-4 text-green-600" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {field.description}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-4 p-3 bg-muted rounded-md">
        <p className="text-xs text-muted-foreground">
          <strong>Note:</strong> At least one of name, netbiosName, or address
          must be mapped for valid asset records.
        </p>
      </div>
    </div>
  )
}
