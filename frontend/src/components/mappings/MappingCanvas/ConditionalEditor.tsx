import { useState, useEffect } from 'react'
import { Plus, X } from 'lucide-react'
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
import type { CanvasConditionRule } from '@/types/canvas'

// The 5 operators exposed in the UI (omit regex/in_list per CONTEXT.md)
type UIOperator = 'equals' | 'not_equals' | 'contains' | 'starts_with' | 'ends_with'

const OPERATOR_LABELS: Record<UIOperator, string> = {
  equals: 'equals',
  not_equals: 'not equals',
  contains: 'contains',
  starts_with: 'starts with',
  ends_with: 'ends with',
}

interface ConditionalEditorProps {
  open: boolean
  sourceField: string        // locked — read-only label
  initialConditions: CanvasConditionRule[]
  initialFallback?: string
  onSave: (conditions: CanvasConditionRule[], fallback: string | undefined) => void
  onCancel: () => void
}

function emptyCondition(sourceField: string): CanvasConditionRule {
  return {
    operator: 'equals',
    source_field: sourceField,
    target_value: '',
    value: '',
  }
}

export function ConditionalEditor({
  open,
  sourceField,
  initialConditions,
  initialFallback,
  onSave,
  onCancel,
}: ConditionalEditorProps) {
  const [localConditions, setLocalConditions] = useState<CanvasConditionRule[]>([])
  const [localFallback, setLocalFallback] = useState<string>('')

  // Reset local state when editor opens
  useEffect(() => {
    if (open) {
      setLocalConditions(initialConditions.length > 0 ? [...initialConditions] : [])
      setLocalFallback(initialFallback ?? '')
    }
  }, [open, initialConditions, initialFallback])

  function addCondition() {
    setLocalConditions((prev) => [...prev, emptyCondition(sourceField)])
  }

  function removeCondition(index: number) {
    setLocalConditions((prev) => prev.filter((_, i) => i !== index))
  }

  function updateCondition(index: number, patch: Partial<CanvasConditionRule>) {
    setLocalConditions((prev) =>
      prev.map((c, i) => (i === index ? { ...c, ...patch } : c))
    )
  }

  function handleSave() {
    onSave(localConditions, localFallback || undefined)
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onCancel() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Conditional mapping</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Source field label (read-only) */}
          <div className="text-sm text-muted-foreground">
            Source field:{' '}
            <span className="font-mono font-medium text-foreground">{sourceField}</span>
          </div>

          {/* Condition rows */}
          <div className="space-y-2">
            {localConditions.length === 0 && (
              <p className="text-xs text-muted-foreground italic">
                No conditions yet. Add one below.
              </p>
            )}
            {localConditions.map((cond, i) => (
              <div
                key={i}
                className="grid grid-cols-[auto_1fr_1fr_1fr_auto] gap-2 items-center"
              >
                {/* Source field label (read-only) */}
                <span className="text-xs font-mono text-muted-foreground truncate max-w-[6rem]">
                  {cond.source_field}
                </span>

                {/* Operator Select */}
                <Select
                  value={cond.operator}
                  onValueChange={(v) => updateCondition(i, { operator: v as UIOperator })}
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(OPERATOR_LABELS) as UIOperator[]).map((op) => (
                      <SelectItem key={op} value={op}>
                        {OPERATOR_LABELS[op]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Match value (target_value) */}
                <Input
                  className="h-7 text-xs"
                  placeholder="match value"
                  value={cond.target_value}
                  onChange={(e) => updateCondition(i, { target_value: e.target.value })}
                />

                {/* Output value (value) */}
                <Input
                  className="h-7 text-xs"
                  placeholder="output value"
                  value={cond.value}
                  onChange={(e) => updateCondition(i, { value: e.target.value })}
                />

                {/* Delete row */}
                <button
                  className="w-5 h-5 flex items-center justify-center rounded hover:bg-destructive/10 text-destructive"
                  aria-label="Remove condition"
                  onClick={() => removeCondition(i)}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>

          {/* Add condition button */}
          <Button variant="outline" size="sm" onClick={addCondition}>
            <Plus className="w-3 h-3 mr-1" />
            Add condition
          </Button>

          {/* Fallback */}
          <div className="space-y-1">
            <label className="text-xs font-medium">Fallback value (optional)</label>
            <Input
              className="h-8 text-xs"
              placeholder="Value when no condition matches"
              value={localFallback}
              onChange={(e) => setLocalFallback(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
