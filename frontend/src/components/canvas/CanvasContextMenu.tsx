import { Plus } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface CanvasContextMenuProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  position: { x: number; y: number }
  onCreateChild: () => void
}

export function CanvasContextMenu({
  open,
  onOpenChange,
  position,
  onCreateChild,
}: CanvasContextMenuProps) {
  return (
    <DropdownMenu open={open} onOpenChange={onOpenChange}>
      <DropdownMenuTrigger asChild>
        <div
          style={{
            position: 'fixed',
            left: position.x,
            top: position.y,
            width: 0,
            height: 0,
            pointerEvents: 'none',
          }}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="bottom">
        <DropdownMenuItem
          onClick={() => {
            onCreateChild()
            onOpenChange(false)
          }}
        >
          <Plus className="h-4 w-4" />
          <span className="text-sm">Create Child Endpoint</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onOpenChange(false)}>
          <span className="text-sm">Cancel</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
