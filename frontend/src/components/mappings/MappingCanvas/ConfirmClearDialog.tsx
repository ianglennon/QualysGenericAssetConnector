import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface ConfirmClearDialogProps {
  open: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmClearDialog({ open, onConfirm, onCancel }: ConfirmClearDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onCancel() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remove all mappings?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Remove all mappings for this endpoint? This cannot be undone.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Keep mappings
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Remove all mappings
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
