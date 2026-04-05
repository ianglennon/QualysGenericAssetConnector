import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '@/providers/AuthProvider'
import {
  useRole,
  useCreateRole,
  useUpdateRole,
  useDeleteRole,
} from '@/hooks/queries/useRoles'
import { PermissionMatrix } from '@/components/settings/PermissionMatrix'
import { ROUTES } from '@/routes/constants'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { toast } from '@/hooks/use-toast'
import { ArrowLeft, Trash2, Loader2 } from 'lucide-react'
import type { AxiosError } from 'axios'

interface ApiErrorDetail {
  error_code: string
  error_message: string
  context?: {
    user_ids?: string[]
  }
}

export function RoleEditPage() {
  const { roleId } = useParams<{ roleId: string }>()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()

  const isCreateMode = roleId === 'new'
  const { data: role, isLoading } = useRole(isCreateMode ? '' : roleId!)

  const createRole = useCreateRole()
  const updateRole = useUpdateRole()
  const deleteRole = useDeleteRole()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  // Populate form fields when role data loads
  useEffect(() => {
    if (role) {
      setName(role.name)
      setDescription(role.description ?? '')
    }
  }, [role])

  const handleCreate = async () => {
    if (!name.trim()) return
    try {
      const result = await createRole.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
      })
      toast({ title: 'Role created', description: `Role "${result.name}" has been created.` })
      navigate(ROUTES.roleEdit(result.id))
    } catch {
      toast({ title: 'Error', description: 'Failed to create role', variant: 'destructive' })
    }
  }

  const handleUpdate = async () => {
    if (!roleId || !name.trim()) return
    try {
      await updateRole.mutateAsync({
        id: roleId,
        payload: {
          name: name.trim(),
          description: description.trim() || undefined,
        },
      })
      toast({ title: 'Role updated', description: 'Role changes have been saved.' })
    } catch {
      toast({ title: 'Error', description: 'Failed to update role', variant: 'destructive' })
    }
  }

  const handleDelete = async () => {
    if (!roleId) return
    setDeleteError('')
    try {
      await deleteRole.mutateAsync(roleId)
      toast({ title: 'Role deleted', description: 'The role has been removed.' })
      navigate(ROUTES.SETTINGS_ROLES)
    } catch (err) {
      const axiosError = err as AxiosError<{ detail: ApiErrorDetail }>
      const detail = axiosError.response?.data?.detail
      if (detail?.error_code === 'ROLE_HAS_USERS') {
        const userIds = detail.context?.user_ids ?? []
        setDeleteError(
          `Cannot delete this role. The following users are still assigned: ${userIds.join(', ')}. Reassign them to another role first.`
        )
      } else {
        setDeleteError(detail?.error_message ?? 'Failed to delete role')
      }
    }
  }

  // Breadcrumb navigation
  const breadcrumb = (
    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-2"
        onClick={() => navigate(ROUTES.SETTINGS_ROLES)}
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Roles
      </Button>
      <span>/</span>
      <span className="text-foreground">
        {isCreateMode ? 'New Role' : role?.name ?? 'Loading...'}
      </span>
    </div>
  )

  // Create mode
  if (isCreateMode) {
    return (
      <div className="space-y-6">
        {breadcrumb}
        <Card>
          <CardHeader>
            <CardTitle>Create New Role</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="role-name">Name</Label>
              <Input
                id="role-name"
                placeholder="Enter role name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role-description">Description (optional)</Label>
              <Input
                id="role-description"
                placeholder="Enter role description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <Button
              onClick={handleCreate}
              disabled={!name.trim() || createRole.isPending}
            >
              {createRole.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Role
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Edit mode - loading
  if (isLoading) {
    return (
      <div className="space-y-6">
        {breadcrumb}
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-48" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </CardContent>
        </Card>
        <Skeleton className="h-[300px] w-full" />
      </div>
    )
  }

  if (!role) {
    return (
      <div className="space-y-6">
        {breadcrumb}
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Role not found.
          </CardContent>
        </Card>
      </div>
    )
  }

  // Edit mode - loaded
  return (
    <div className="space-y-6">
      {breadcrumb}

      <Card>
        <CardHeader>
          <CardTitle>{role.name}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="role-name">Name</Label>
            <Input
              id="role-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={role.is_system}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role-description">Description</Label>
            <Input
              id="role-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={role.is_system}
            />
          </div>
          {!role.is_system && (
            <Button
              onClick={handleUpdate}
              disabled={!name.trim() || updateRole.isPending}
            >
              {updateRole.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          )}
        </CardContent>
      </Card>

      <Separator />

      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Permissions</h3>
        <PermissionMatrix
          roleId={roleId!}
          permissions={role.permissions}
          disabled={role.is_system}
        />
      </div>

      {!role.is_system && hasPermission('roles:delete') && (
        <>
          <Separator />
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-destructive">Danger Zone</h3>
            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Role
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete {role.name}?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                {deleteError && (
                  <p className="text-destructive text-sm mt-2">{deleteError}</p>
                )}
                <AlertDialogFooter>
                  <AlertDialogCancel onClick={() => setDeleteError('')}>
                    Cancel
                  </AlertDialogCancel>
                  <AlertDialogAction
                    onClick={(e) => {
                      e.preventDefault()
                      handleDelete()
                    }}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    disabled={deleteRole.isPending}
                  >
                    {deleteRole.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </>
      )}
    </div>
  )
}
