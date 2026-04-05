import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Copy, Check } from 'lucide-react'
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
import { useCreateUser } from '@/hooks/queries/useUsers'
import { useRoles } from '@/hooks/queries/useRoles'
import type { UserCreateResponse } from '@/hooks/queries/useUsers'

const createUserSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  role_id: z.string().min(1, 'Role is required'),
})

type CreateUserForm = z.infer<typeof createUserSchema>

interface UserCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function UserCreateDialog({ open, onOpenChange }: UserCreateDialogProps) {
  const [createdUser, setCreatedUser] = useState<UserCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const createUser = useCreateUser()
  const { data: roles } = useRoles()

  const form = useForm<CreateUserForm>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { email: '', role_id: '' },
  })

  const handleSubmit = async (values: CreateUserForm) => {
    setErrorMessage(null)
    try {
      const response = await createUser.mutateAsync(values)
      setCreatedUser(response)
    } catch (error: any) {
      const message =
        error.response?.data?.detail?.error_message ??
        error.response?.data?.detail ??
        'Failed to create user'
      setErrorMessage(typeof message === 'string' ? message : 'Failed to create user')
    }
  }

  const handleCopy = async () => {
    if (!createdUser) return
    await navigator.clipboard.writeText(createdUser.temporary_password)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleClose = (isOpen: boolean) => {
    if (!isOpen) {
      setCreatedUser(null)
      setCopied(false)
      setErrorMessage(null)
      form.reset()
    }
    onOpenChange(isOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        {createdUser ? (
          <>
            <DialogHeader>
              <DialogTitle>User Created</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Account created for <strong>{createdUser.email}</strong>.
              </p>
              <div>
                <Label className="text-sm font-medium">Temporary Password</Label>
                <code className="block bg-muted p-3 rounded font-mono text-sm mt-1">
                  {createdUser.temporary_password}
                </code>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="w-full"
              >
                {copied ? (
                  <>
                    <Check className="mr-2 h-4 w-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy Password
                  </>
                )}
              </Button>
              <p className="text-sm text-muted-foreground">
                The user must change this password on first login.
              </p>
            </div>
            <DialogFooter>
              <Button onClick={() => handleClose(false)}>Done</Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Add User</DialogTitle>
            </DialogHeader>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="user@example.com"
                  {...form.register('email')}
                />
                {form.formState.errors.email && (
                  <p className="text-destructive text-sm">
                    {form.formState.errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
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
                  onClick={() => handleClose(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createUser.isPending}>
                  {createUser.isPending ? 'Creating...' : 'Create'}
                </Button>
              </DialogFooter>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
