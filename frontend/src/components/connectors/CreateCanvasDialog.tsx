import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface CreateCanvasDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (name: string, description?: string) => void
  isPending?: boolean
  error?: string | null
}

export function CreateCanvasDialog({ open, onOpenChange, onSubmit, isPending, error }: CreateCanvasDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onSubmit(name.trim(), description.trim() || undefined)
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setName('')
      setDescription('')
    }
    onOpenChange(isOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Canvas</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="canvas-name">Name</Label>
            <Input
              id="canvas-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Canvas name"
              maxLength={100}
              disabled={isPending}
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="canvas-description">Description (optional)</Label>
            <Input
              id="canvas-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe this data flow"
              maxLength={500}
              disabled={isPending}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim() || isPending}>
              {isPending ? 'Creating...' : 'Create Canvas'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
