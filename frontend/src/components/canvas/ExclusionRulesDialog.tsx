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
import type { ExclusionRule } from '@/types/canvas'

const OPERATOR_LABELS: Record<ExclusionRule['operator'], string> = {
  equals: 'equals',
  not_equals: 'not equals',
  contains: 'contains',
  starts_with: 'starts with',
  ends_with: 'ends with',
  regex: 'regex',
  in_list: 'in list',
}

const OPERATORS = Object.keys(OPERATOR_LABELS) as ExclusionRule['operator'][]

function emptyRule(): ExclusionRule {
  return { source_field: '', operator: 'equals', value: '' }
}

interface ExclusionRulesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  rules: ExclusionRule[]
  onSave: (rules: ExclusionRule[]) => void
  fieldSuggestions: string[]
}

export function ExclusionRulesDialog({
  open,
  onOpenChange,
  rules,
  onSave,
  fieldSuggestions,
}: ExclusionRulesDialogProps) {
  const [draftRules, setDraftRules] = useState<ExclusionRule[]>([emptyRule()])

  // Reset draft when dialog opens
  useEffect(() => {
    if (open) {
      setDraftRules(rules.length > 0 ? rules.map((r) => ({ ...r })) : [emptyRule()])
    }
  }, [open, rules])

  const updateRule = (index: number, field: keyof ExclusionRule, val: string) => {
    setDraftRules((prev) =>
      prev.map((r, i) =>
        i === index
          ? { ...r, [field]: field === 'operator' ? (val as ExclusionRule['operator']) : val }
          : r,
      ),
    )
  }

  const removeRule = (index: number) => {
    setDraftRules((prev) => {
      const next = prev.filter((_, i) => i !== index)
      return next.length > 0 ? next : [emptyRule()]
    })
  }

  const addRule = () => {
    setDraftRules((prev) => [...prev, emptyRule()])
  }

  const hasIncomplete = draftRules.some(
    (r) => r.source_field.trim() === '' || r.value.trim() === '',
  )

  const handleSave = () => {
    const valid = draftRules.filter((r) => r.source_field.trim() && r.value.trim())
    onSave(valid)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Exclusion Rules</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Records matching any rule will be excluded from processing.
          </p>
        </DialogHeader>

        <div className="flex flex-col gap-2">
          {draftRules.map((rule, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                list={`exclusion-fields-${index}`}
                placeholder="e.g. template"
                className="flex-1"
                value={rule.source_field}
                onChange={(e) => updateRule(index, 'source_field', e.target.value)}
              />
              <datalist id={`exclusion-fields-${index}`}>
                {fieldSuggestions.map((f) => (
                  <option key={f} value={f} />
                ))}
              </datalist>

              <Select
                value={rule.operator}
                onValueChange={(val) => updateRule(index, 'operator', val)}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OPERATORS.map((op) => (
                    <SelectItem key={op} value={op}>
                      {OPERATOR_LABELS[op]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Input
                placeholder="Match value"
                className="flex-1"
                value={rule.value}
                onChange={(e) => updateRule(index, 'value', e.target.value)}
              />

              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                aria-label="Remove rule"
                onClick={() => removeRule(index)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>

        <Button variant="outline" size="sm" onClick={addRule}>
          <Plus className="h-4 w-4 mr-1" />
          Add Rule
        </Button>

        {hasIncomplete && draftRules.length > 0 && (
          <p className="text-xs text-destructive">All fields are required to save.</p>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Discard Changes
          </Button>
          <Button variant="default" disabled={hasIncomplete} onClick={handleSave}>
            Save Filters
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
