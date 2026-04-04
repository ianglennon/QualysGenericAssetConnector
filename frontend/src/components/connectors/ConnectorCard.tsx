import { useNavigate } from 'react-router-dom'
import { ROUTES } from '@/routes/constants'
import { MoreVertical, Play, Check, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { ScheduleBadge } from '@/components/connectors/ScheduleBadge'
import { useAuth } from '@/hooks/useAuth'
import type { Connector } from '@/types/api'

interface ConnectorCardProps {
  connector: Connector
  onEdit?: (connector: Connector) => void
  onDelete?: (connector: Connector) => void
  onTriggerSync?: (connector: Connector) => void
  isSyncSucceeded?: boolean
}

export function ConnectorCard({ connector, onEdit, onDelete, onTriggerSync, isSyncSucceeded }: ConnectorCardProps) {
  const { user } = useAuth()
  const navigate = useNavigate()

  const isAdmin = user?.role === 'admin'

  return (
    <Card className="cursor-pointer hover:border-primary/50 transition-colors" onClick={() => navigate(ROUTES.connectorDetail(connector.id))}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-lg font-medium">{connector.name}</CardTitle>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {onTriggerSync && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onTriggerSync(connector)}
              disabled={!connector.has_valid_endpoints || isSyncSucceeded}
              title={
                isSyncSucceeded ? 'Sync triggered'
                : connector.has_valid_endpoints ? 'Trigger Sync'
                : 'Connector has invalid endpoint mappings'
              }
              className={isSyncSucceeded ? 'text-green-600' : ''}
            >
              {isSyncSucceeded ? <Check className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>
          )}
          {isAdmin && (onEdit || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onEdit && (
                  <DropdownMenuItem onClick={() => onEdit(connector)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <DropdownMenuItem
                    onClick={() => onDelete(connector)}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="text-sm text-muted-foreground">{connector.base_url}</div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="capitalize">
              {connector.auth_method.replace('_', ' ')}
            </Badge>
            <Badge variant={connector.has_token || connector.has_username || connector.has_api_key ? 'default' : 'secondary'}>
              {connector.has_token || connector.has_username || connector.has_api_key ? 'Configured' : 'No Auth'}
            </Badge>
            {connector.has_valid_endpoints ? (
              <Badge variant="outline" className="border-green-600 text-green-600">Ready</Badge>
            ) : (
              <Badge variant="outline" className="border-amber-500 text-amber-600">Invalid</Badge>
            )}
          </div>
          <ScheduleBadge connector={connector} />
        </div>
      </CardContent>
    </Card>
  )
}
