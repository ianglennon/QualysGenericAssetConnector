import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog'
import { useDeactivateUser } from '@/hooks/queries/useUsers'
import { useToast } from '@/hooks/use-toast'
import type { UserResponse } from '@/hooks/queries/useUsers'

interface UserDeactivateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: UserResponse | null
}

export function UserDeactivateDialog({ open, onOpenChange, user }: UserDeactivateDialogProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const deactivateUser = useDeactivateUser()
  const { toast } = useToast()

  const handleDeactivate = async () => {
    if (!user) return
    setErrorMessage(null)
    try {
      await deactivateUser.mutateAsync(user.id)
      onOpenChange(false)
      setErrorMessage(null)
      toast({
        title: 'User deactivated',
        description: `${user.email} has been deactivated.`,
      })
    } catch (error: any) {
      const message =
        error.response?.data?.detail?.error_message ??
        error.response?.data?.detail ??
        'Failed to deactivate user'
      setErrorMessage(typeof message === 'string' ? message : 'Failed to deactivate user')
    }
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setErrorMessage(null)
    }
    onOpenChange(isOpen)
  }

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Deactivate {user?.email}?</AlertDialogTitle>
          <AlertDialogDescription>
            This user will no longer be able to log in. Run history will be preserved.
          </AlertDialogDescription>
        </AlertDialogHeader>

        {errorMessage && (
          <p className="text-destructive text-sm mt-2">{errorMessage}</p>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel>Keep User</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDeactivate}
            disabled={deactivateUser.isPending}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {deactivateUser.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deactivating...
              </>
            ) : (
              'Deactivate'
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
