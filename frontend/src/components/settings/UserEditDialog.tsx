import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUpdateUser } from '@/hooks/queries/useUsers'
import { useRoles } from '@/hooks/queries/useRoles'
import { useToast } from '@/hooks/use-toast'
import type { UserResponse } from '@/hooks/queries/useUsers'

const editUserSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  role_id: z.string().min(1, 'Role is required'),
})

type EditUserForm = z.infer<typeof editUserSchema>

interface UserEditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: UserResponse | null
}

export function UserEditDialog({ open, onOpenChange, user }: UserEditDialogProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const updateUser = useUpdateUser()
  const { data: roles } = useRoles()
  const { toast } = useToast()

  const form = useForm<EditUserForm>({
    resolver: zodResolver(editUserSchema),
    defaultValues: { email: '', role_id: '' },
  })

  useEffect(() => {
    if (user && open) {
      form.reset({
        email: user.email,
        role_id: user.role.id,
      })
      setErrorMessage(null)
    }
  }, [user, open, form])

  const handleSubmit = async (values: EditUserForm) => {
    if (!user) return
    setErrorMessage(null)
    try {
      await updateUser.mutateAsync({
        id: user.id,
        payload: { email: values.email, role_id: values.role_id },
      })
      onOpenChange(false)
      toast({
        title: 'User updated',
        description: `${values.email} has been updated successfully.`,
      })
    } catch (error: any) {
      const message =
        error.response?.data?.detail?.error_message ??
        error.response?.data?.detail ??
        'Failed to update user'
      setErrorMessage(typeof message === 'string' ? message : 'Failed to update user')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit User</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-email">Email</Label>
            <Input
              id="edit-email"
              type="email"
              {...form.register('email')}
            />
            {form.formState.errors.email && (
              <p className="text-destructive text-sm">
                {form.formState.errors.email.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-role">Role</Label>
            <Select
              value={form.watch('role_id')}
              onValueChange={(value) => form.setValue('role_id', value, { shouldValidate: true })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a role" />
              </SelectTrigger>
              <SelectContent>
                {roles?.map((role) => (
                  <SelectItem key={role.id} value={role.id}>
                    {role.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.formState.errors.role_id && (
              <p className="text-destructive text-sm">
                {form.formState.errors.role_id.message}
              </p>
            )}
          </div>

          {errorMessage && (
            <p className="text-destructive text-sm">{errorMessage}</p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={updateUser.isPending}>
              {updateUser.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
