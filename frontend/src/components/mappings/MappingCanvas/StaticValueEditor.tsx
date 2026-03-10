import { useState, useEffect } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { StaticValueType } from '@/types/canvas'

interface StaticValueEditorProps {
  open: boolean
  onClose: () => void
  anchorRef: React.RefObject<HTMLSpanElement | null>
  sourceField: string
  initialValue?: string | number | boolean
  initialType?: StaticValueType
  onSave: (value: string | number | boolean, valueType: StaticValueType) => void
  onCancel: () => void
}

export function StaticValueEditor({
  open,
  anchorRef,
  sourceField,
  initialValue,
  initialType,
  onSave,
  onCancel,
}: StaticValueEditorProps) {
  const [localType, setLocalType] = useState<StaticValueType>(initialType ?? 'string')
  const [localValue, setLocalValue] = useState<string>(
    initialValue !== undefined ? String(initialValue) : ''
  )

  // Reset local state when editor opens
  useEffect(() => {
    if (open) {
      setLocalType(initialType ?? 'string')
      setLocalValue(initialValue !== undefined ? String(initialValue) : '')
    }
  }, [open, initialValue, initialType])

  function handleSave() {
    let parsed: string | number | boolean = localValue
    if (localType === 'number') {
      parsed = localValue === '' ? 0 : Number(localValue)
    } else if (localType === 'boolean') {
      parsed = localValue === 'true'
    }
    onSave(parsed, localType)
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={(v) => { if (!v) onCancel() }}>
      <PopoverPrimitive.Anchor asChild>
        <span
          ref={anchorRef as React.RefObject<HTMLSpanElement>}
          style={{ position: 'absolute', pointerEvents: 'none' }}
        />
      </PopoverPrimitive.Anchor>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          side="bottom"
          align="center"
          sideOffset={4}
          className="z-50 w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <div className="space-y-3">
            <div>
              <p className="text-xs text-muted-foreground mb-1">
                Source: <span className="font-mono font-medium">{sourceField}</span>
              </p>
            </div>

            {/* Value type selector */}
            <div className="space-y-1">
              <label className="text-xs font-medium">Value type</label>
              <Select
                value={localType}
                onValueChange={(v) => {
                  setLocalType(v as StaticValueType)
                  setLocalValue('')
                }}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="string">String</SelectItem>
                  <SelectItem value="number">Number</SelectItem>
                  <SelectItem value="boolean">Boolean</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Value input */}
            <div className="space-y-1">
              <label className="text-xs font-medium">Value</label>
              {localType === 'boolean' ? (
                <Select
                  value={localValue || 'true'}
                  onValueChange={(v) => setLocalValue(v)}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">true</SelectItem>
                    <SelectItem value="false">false</SelectItem>
                  </SelectContent>
                </Select>
              ) : localType === 'number' ? (
                <Input
                  type="number"
                  className="h-8 text-xs"
                  value={localValue}
                  onChange={(e) => setLocalValue(e.target.value)}
                  placeholder="Enter number..."
                />
              ) : (
                <Input
                  type="text"
                  className="h-8 text-xs"
                  value={localValue}
                  onChange={(e) => setLocalValue(e.target.value)}
                  placeholder="Enter value..."
                />
              )}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-1">
              <Button variant="outline" size="sm" onClick={onCancel}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave}>
                Save
              </Button>
            </div>
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
