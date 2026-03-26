import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import type { CollectConfig } from '@/types/canvas'

const FILTER_OPERATORS = [
  { value: 'equals', label: 'equals' },
  { value: 'not_equals', label: 'not equals' },
  { value: 'contains', label: 'contains' },
  { value: 'starts_with', label: 'starts with' },
  { value: 'ends_with', label: 'ends with' },
  { value: 'regex', label: 'regex' },
  { value: 'in_list', label: 'in list' },
] as const

interface CollectEditorProps {
  open: boolean
  initialConfig: CollectConfig
  onSave: (config: CollectConfig) => void
  onCancel: () => void
}

export function CollectEditor({
  open,
  initialConfig,
  onSave,
  onCancel,
}: CollectEditorProps) {
  const [arrayPath, setArrayPath] = useState(initialConfig.array_path || '')
  const [extractField, setExtractField] = useState(initialConfig.extract_field || '')
  const [separator, setSeparator] = useState(initialConfig.separator || '')
  const [filterOp, setFilterOp] = useState(initialConfig.filter?.operator || 'equals')
  const [filterValue, setFilterValue] = useState(initialConfig.filter?.value || '')
  const [hasFilter, setHasFilter] = useState(!!initialConfig.filter)

  // Sync state when dialog opens or initialConfig changes
  useEffect(() => {
    if (open) {
      setArrayPath(initialConfig.array_path || '')
      setExtractField(initialConfig.extract_field || '')
      setSeparator(initialConfig.separator || '')
      setFilterOp(initialConfig.filter?.operator || 'equals')
      setFilterValue(initialConfig.filter?.value || '')
      setHasFilter(!!initialConfig.filter)
    }
  }, [open, initialConfig])

  function handleSave() {
    onSave({
      array_path: arrayPath,
      extract_field: extractField || undefined,
      filter: hasFilter
        ? { field: extractField, operator: filterOp, value: filterValue }
        : undefined,
      separator: separator || undefined,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onCancel() }}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Collect mapping</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Row 1: Array path */}
          <div className="space-y-1">
            <label className="text-xs font-medium">Array path</label>
            <Input
              className="font-mono"
              value={arrayPath}
              onChange={(e) => setArrayPath(e.target.value)}
              readOnly={!!initialConfig.array_path}
            />
          </div>

          {/* Row 2: Extract field */}
          <div className="space-y-1">
            <label className="text-xs font-medium">Extract field</label>
            <Input
              className="font-mono"
              value={extractField}
              onChange={(e) => setExtractField(e.target.value)}
            />
          </div>

          {/* Row 3: Separator */}
          <div className="space-y-1">
            <label className="text-xs font-medium">Separator</label>
            <Input
              placeholder="optional"
              value={separator}
              onChange={(e) => setSeparator(e.target.value)}
            />
          </div>

          {/* Row 4: Filter section */}
          <div className="space-y-2">
            {hasFilter ? (
              <div className="grid grid-cols-[auto_1fr_1fr_auto] gap-2 items-center">
                <span className="font-mono text-sm text-muted-foreground truncate max-w-[8rem]">
                  {extractField || '(field)'}
                </span>
                <Select value={filterOp} onValueChange={setFilterOp}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FILTER_OPERATORS.map((op) => (
                      <SelectItem key={op.value} value={op.value}>
                        {op.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  className="h-8 text-xs"
                  placeholder="filter value"
                  value={filterValue}
                  onChange={(e) => setFilterValue(e.target.value)}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  aria-label="Remove filter"
                  onClick={() => {
                    setHasFilter(false)
                    setFilterOp('equals')
                    setFilterValue('')
                  }}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ) : extractField ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setHasFilter(true)}
              >
                Add filter
              </Button>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                No filter applied. All array elements will be collected.
              </p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Discard changes
          </Button>
          <Button onClick={handleSave}>
            Save collect mapping
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
