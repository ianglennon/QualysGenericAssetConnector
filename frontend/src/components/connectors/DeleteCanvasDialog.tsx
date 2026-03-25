import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import type { CanvasListItem } from '@/types/canvas'

interface DeleteCanvasDialogProps {
  canvas: CanvasListItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isPending?: boolean
}

export function DeleteCanvasDialog({ canvas, open, onOpenChange, onConfirm, isPending }: DeleteCanvasDialogProps) {
  if (!canvas) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Canvas</DialogTitle>
          <DialogDescription>
            This will permanently delete <strong>{canvas.name}</strong> along with{' '}
            {canvas.endpoint_count} endpoint {canvas.endpoint_count === 1 ? 'reference' : 'references'} and{' '}
            {canvas.field_mapping_count} field {canvas.field_mapping_count === 1 ? 'mapping' : 'mappings'}.
            Shared endpoint definitions will not be deleted.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Keep Canvas
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
            {isPending ? 'Deleting...' : 'Delete Canvas'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
