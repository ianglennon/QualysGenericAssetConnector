import { useParams } from 'react-router-dom'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useConnector } from '@/hooks/queries/useConnectors'

export function ConnectorDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: connector, isLoading } = useConnector(id)

  if (isLoading) {
    return (
      <PageContainer title="Loading...">
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-32 w-full" />
        </div>
      </PageContainer>
    )
  }

  if (!connector) {
    return (
      <PageContainer title="Connector Not Found">
        <p className="text-muted-foreground">The connector you're looking for doesn't exist.</p>
      </PageContainer>
    )
  }

  return (
    <PageContainer
      title={connector.name}
      actions={
        <div className="flex gap-2">
          <Button variant="outline">Edit</Button>
          <Button variant="outline">Test</Button>
          <Button>Trigger Sync</Button>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="rounded-lg border p-6 space-y-4">
          <div>
            <h3 className="text-sm font-medium text-muted-foreground">Base URL</h3>
            <p className="text-sm">{connector.base_url}</p>
          </div>

          {connector.test_path && (
            <div>
              <h3 className="text-sm font-medium text-muted-foreground">Test Path</h3>
              <p className="text-sm">{connector.test_path}</p>
            </div>
          )}

          <div>
            <h3 className="text-sm font-medium text-muted-foreground">Authentication</h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline" className="capitalize">
                {connector.auth_method.replace('_', ' ')}
              </Badge>
              {(connector.has_token || connector.has_username || connector.has_api_key) && (
                <Badge variant="default">Configured</Badge>
              )}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-muted-foreground">Pagination Strategies</h3>
            <p className="text-sm">
              {connector.pagination_strategies.length === 0
                ? 'No pagination (single page)'
                : `${connector.pagination_strategies.length} strateg${connector.pagination_strategies.length === 1 ? 'y' : 'ies'} configured`}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-4 border-t">
            <div>
              <h3 className="text-sm font-medium text-muted-foreground">Created</h3>
              <p className="text-sm">{new Date(connector.created_at).toLocaleString()}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-muted-foreground">Last Updated</h3>
              <p className="text-sm">{new Date(connector.updated_at).toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
