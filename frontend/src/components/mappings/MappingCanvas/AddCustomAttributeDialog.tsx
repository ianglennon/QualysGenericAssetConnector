import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

const KEY_PATTERN = /^[a-zA-Z0-9_-]+$/
const MAX_KEY_LENGTH = 64

interface AddCustomAttributeDialogProps {
  open: boolean
  existingKeys: Set<string>  // set of existing customAttribute.{key} field names
  onAdd: (key: string) => void
  onClose: () => void
}

export function AddCustomAttributeDialog({ open, existingKeys, onAdd, onClose }: AddCustomAttributeDialogProps) {
  const [key, setKey] = useState('')

  function getError(): string | null {
    if (!key) return null
    if (!KEY_PATTERN.test(key)) {
      return 'Attribute key must contain only letters, numbers, underscores, and hyphens.'
    }
    if (key.length > MAX_KEY_LENGTH) {
      return `Attribute key must be ${MAX_KEY_LENGTH} characters or fewer.`
    }
    if (existingKeys.has(`customAttribute.${key}`)) {
      return `A custom attribute with key "${key}" already exists.`
    }
    return null
  }

  const error = getError()
  const canSubmit = key.length > 0 && error === null

  function handleSubmit() {
    if (!canSubmit) return
    onAdd(key)
    setKey('')
    onClose()
  }

  function handleOpenChange(open: boolean) {
    if (!open) {
      setKey('')
      onClose()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add custom attribute</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="attr-key">Attribute key</Label>
          <Input
            id="attr-key"
            autoFocus
            placeholder="e.g. environment, cost_center, team"
            value={key}
            onChange={e => setKey(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSubmit() }}
          />
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Discard
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            Add attribute
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
