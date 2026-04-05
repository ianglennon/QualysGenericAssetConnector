import { useState, useMemo } from 'react'
import { Plus, Pencil, Ban, ArrowUpDown } from 'lucide-react'
import { format } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useUsers } from '@/hooks/queries/useUsers'
import { useAuth } from '@/hooks/useAuth'
import { UserCreateDialog } from '@/components/settings/UserCreateDialog'
import { UserEditDialog } from '@/components/settings/UserEditDialog'
import { UserDeactivateDialog } from '@/components/settings/UserDeactivateDialog'
import type { UserResponse } from '@/hooks/queries/useUsers'

type SortField = 'email' | 'role' | 'status' | 'created_at'
type SortDirection = 'asc' | 'desc'

export function UsersPage() {
  const { user: currentUser, hasPermission } = useAuth()
  const { data: users, isLoading } = useUsers()

  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deactivateOpen, setDeactivateOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null)
  const [sortField, setSortField] = useState<SortField>('email')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const sortedUsers = useMemo(() => {
    if (!users) return []
    const sorted = [...users].sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case 'email':
          cmp = a.email.localeCompare(b.email)
          break
        case 'role':
          cmp = a.role.name.localeCompare(b.role.name)
          break
        case 'status':
          cmp = Number(b.is_active) - Number(a.is_active)
          break
        case 'created_at':
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          break
      }
      return sortDirection === 'asc' ? cmp : -cmp
    })
    return sorted
  }, [users, sortField, sortDirection])

  const handleEdit = (user: UserResponse) => {
    setSelectedUser(user)
    setEditOpen(true)
  }

  const handleDeactivate = (user: UserResponse) => {
    setSelectedUser(user)
    setDeactivateOpen(true)
  }

  const SortableHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <TableHead>
      <button
        type="button"
        className="flex items-center gap-1 hover:text-foreground transition-colors"
        onClick={() => handleSort(field)}
      >
        {children}
        <ArrowUpDown className="h-3 w-3" />
      </button>
    </TableHead>
  )

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        {hasPermission('users:create') && (
          <div className="flex justify-end">
            <Skeleton className="h-10 w-28" />
          </div>
        )}
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    )
  }

  if (!users || users.length === 0) {
    return (
      <div className="p-6">
        <Card className="flex flex-col items-center justify-center p-12 text-center">
          <h3 className="text-lg font-semibold">No user accounts yet</h3>
          <p className="text-sm text-muted-foreground mt-2">
            Create a user account to get started.
          </p>
          {hasPermission('users:create') && (
            <Button className="mt-4" onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add User
            </Button>
          )}
        </Card>
        <UserCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      </div>
    )
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex justify-end">
        {hasPermission('users:create') && (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add User
          </Button>
        )}
      </div>

      <TooltipProvider>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableHeader field="email">Email</SortableHeader>
                <SortableHeader field="role">Role</SortableHeader>
                <SortableHeader field="status">Status</SortableHeader>
                <SortableHeader field="created_at">Created</SortableHeader>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedUsers.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.email}</TableCell>
                  <TableCell>{user.role.name}</TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? 'default' : 'secondary'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>{format(new Date(user.created_at), 'MMM d, yyyy')}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {hasPermission('users:update') && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleEdit(user)}
                              aria-label={`Edit ${user.email}`}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Edit user</TooltipContent>
                        </Tooltip>
                      )}
                      {hasPermission('users:update') && user.id !== currentUser?.id && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeactivate(user)}
                              aria-label={`Deactivate ${user.email}`}
                            >
                              <Ban className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Deactivate user</TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </TooltipProvider>

      <UserCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
      <UserEditDialog open={editOpen} onOpenChange={setEditOpen} user={selectedUser} />
      <UserDeactivateDialog open={deactivateOpen} onOpenChange={setDeactivateOpen} user={selectedUser} />
    </div>
  )
}
