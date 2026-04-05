import { useState, useEffect } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAddPermission, useRemovePermission } from '@/hooks/queries/useRoles'
import { toast } from '@/hooks/use-toast'

const RESOURCE_AREAS = ['connectors', 'canvases', 'schedules', 'runs', 'settings', 'users', 'roles'] as const
const CRUD_ACTIONS = ['create', 'read', 'update', 'delete'] as const
const SPECIAL_ACTIONS: Record<string, string> = {
  connectors: 'toggle_enabled',
  runs: 'trigger_sync',
}
const RESOURCE_LABELS: Record<string, string> = {
  connectors: 'Connectors',
  canvases: 'Canvases',
  schedules: 'Schedules',
  runs: 'Runs',
  settings: 'Settings',
  users: 'Users',
  roles: 'Roles',
}

interface PermissionMatrixProps {
  roleId: string
  permissions: string[]
  disabled: boolean
}

export function PermissionMatrix({ roleId, permissions, disabled }: PermissionMatrixProps) {
  const [localPermissions, setLocalPermissions] = useState<string[]>(permissions)
  const addPermission = useAddPermission()
  const removePermission = useRemovePermission()

  // Sync localPermissions with permissions prop when it changes
  useEffect(() => {
    setLocalPermissions(permissions)
  }, [permissions])

  const handleToggle = async (permission: string, checked: boolean) => {
    if (disabled) return

    const prev = [...localPermissions]
    // Optimistic update
    setLocalPermissions(checked ? [...prev, permission] : prev.filter(p => p !== permission))

    try {
      if (checked) {
        await addPermission.mutateAsync({ roleId, permissions: [permission] })
      } else {
        await removePermission.mutateAsync({ roleId, permission })
      }
    } catch {
      setLocalPermissions(prev) // Revert
      toast({
        title: 'Error',
        description: 'Failed to update permission',
        variant: 'destructive',
      })
    }
  }

  return (
    <TooltipProvider>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[140px]">Resource</TableHead>
              {CRUD_ACTIONS.map((action) => (
                <TableHead key={action} className="text-center capitalize w-[90px]">
                  {action}
                </TableHead>
              ))}
              <TableHead className="text-center w-[90px]">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="cursor-help underline decoration-dotted">Special</span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Additional actions beyond CRUD</p>
                  </TooltipContent>
                </Tooltip>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {RESOURCE_AREAS.map((resource) => (
              <TableRow key={resource}>
                <TableCell className="font-medium">
                  {RESOURCE_LABELS[resource]}
                </TableCell>
                {CRUD_ACTIONS.map((action) => {
                  const permission = `${resource}:${action}`
                  return (
                    <TableCell key={action} className="text-center">
                      <Checkbox
                        id={permission}
                        aria-label={permission}
                        checked={disabled || localPermissions.includes(permission)}
                        onCheckedChange={(checked: boolean) => handleToggle(permission, !!checked)}
                        disabled={disabled}
                      />
                    </TableCell>
                  )
                })}
                <TableCell className="text-center">
                  {SPECIAL_ACTIONS[resource] ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span>
                          <Checkbox
                            id={`${resource}:${SPECIAL_ACTIONS[resource]}`}
                            aria-label={`${resource}:${SPECIAL_ACTIONS[resource]}`}
                            checked={
                              disabled ||
                              localPermissions.includes(`${resource}:${SPECIAL_ACTIONS[resource]}`)
                            }
                            onCheckedChange={(checked: boolean) =>
                              handleToggle(`${resource}:${SPECIAL_ACTIONS[resource]}`, !!checked)
                            }
                            disabled={disabled}
                          />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>{SPECIAL_ACTIONS[resource]}</p>
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span className="text-muted-foreground">---</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </TooltipProvider>
  )
}
