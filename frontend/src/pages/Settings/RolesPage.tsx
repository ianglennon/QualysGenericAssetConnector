import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/providers/AuthProvider'
import { useRoles, type RoleListResponse } from '@/hooks/queries/useRoles'
import { ROUTES } from '@/routes/constants'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Pencil, Eye, Plus, ArrowUpDown } from 'lucide-react'

type SortField = 'name' | 'user_count'
type SortDirection = 'asc' | 'desc'

export function RolesPage() {
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { data: roles, isLoading } = useRoles()
  const [sortField, setSortField] = useState<SortField>('name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')

  const sortedRoles = useMemo(() => {
    if (!roles) return []
    return [...roles].sort((a, b) => {
      let cmp = 0
      if (sortField === 'name') {
        cmp = a.name.localeCompare(b.name)
      } else {
        cmp = a.user_count - b.user_count
      }
      return sortDirection === 'asc' ? cmp : -cmp
    })
  }, [roles, sortField, sortDirection])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-9 w-28" />
        </div>
        <div className="rounded-md border">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-4 p-4 border-b last:border-0">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-8 w-8 ml-auto" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!roles || roles.length === 0) {
    return (
      <div className="space-y-4">
        {hasPermission('roles:create') && (
          <div className="flex justify-end">
            <Button onClick={() => navigate(ROUTES.roleEdit('new'))}>
              <Plus className="mr-2 h-4 w-4" />
              Create Role
            </Button>
          </div>
        )}
        <Card>
          <CardHeader className="text-center">
            <CardTitle>No custom roles</CardTitle>
            <CardDescription>
              Create a role to assign granular permissions to users.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <div className="space-y-4">
        {hasPermission('roles:create') && (
          <div className="flex justify-end">
            <Button onClick={() => navigate(ROUTES.roleEdit('new'))}>
              <Plus className="mr-2 h-4 w-4" />
              Create Role
            </Button>
          </div>
        )}
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="-ml-3 h-8"
                    onClick={() => handleSort('name')}
                  >
                    Name
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                  </Button>
                </TableHead>
                <TableHead>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="-ml-3 h-8"
                    onClick={() => handleSort('user_count')}
                  >
                    Users
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                  </Button>
                </TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRoles.map((role: RoleListResponse) => (
                <TableRow
                  key={role.id}
                  className="cursor-pointer"
                  onClick={() => navigate(ROUTES.roleEdit(role.id))}
                >
                  <TableCell className="font-medium">{role.name}</TableCell>
                  <TableCell>{role.user_count}</TableCell>
                  <TableCell>
                    <Badge variant={role.is_system ? 'secondary' : 'default'}>
                      {role.is_system ? 'Built-in' : 'Custom'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {hasPermission('roles:read') && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(ROUTES.roleEdit(role.id))
                            }}
                          >
                            {role.is_system ? (
                              <Eye className="h-4 w-4" />
                            ) : (
                              <Pencil className="h-4 w-4" />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {role.is_system ? 'View role' : 'Edit role'}
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </TooltipProvider>
  )
}
