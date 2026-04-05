import { Plus } from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageContainer } from '@/components/layout/PageContainer'
import { useAuth } from '@/hooks/useAuth'
import { useConnectors } from '@/hooks/queries/useConnectors'
import { useRunStats } from '@/hooks/queries/useRunStats'

export default function Dashboard() {
  const { user, hasPermission } = useAuth()
  const { data: connectors = [] } = useConnectors()
  const { data: stats } = useRunStats()

  return (
    <PageContainer
      title="Dashboard"
      actions={
        hasPermission('connectors:create') ? (
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Connector
          </Button>
        ) : undefined
      }
    >
      <div className="space-y-6">
        {/* Welcome Card */}
        <Card>
          <CardHeader>
            <CardTitle>Welcome back, {user?.email}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Role: <span className="capitalize font-medium">{user?.role.name}</span>
            </p>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Connectors</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{connectors.length}</div>
              <p className="text-xs text-muted-foreground">
                Active integrations
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Recent Runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.recent_runs_24h ?? 0}</div>
              <p className="text-xs text-muted-foreground">
                In the last 24 hours
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(!stats || stats.total_runs === 0) ? '—' : `${Math.round(stats.success_rate * 100)}%`}
              </div>
              <p className="text-xs text-muted-foreground">
                {(!stats || stats.total_runs === 0) ? 'No runs yet' : 'All-time success rate'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Last Sync</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className="text-2xl font-bold"
                title={stats?.last_sync_at ? format(new Date(stats.last_sync_at), 'MMM d, yyyy h:mm:ss a') : undefined}
                style={stats?.last_sync_at ? { cursor: 'help' } : undefined}
              >
                {stats?.last_sync_at ? formatDistanceToNow(new Date(stats.last_sync_at), { addSuffix: true }) : '—'}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats?.last_sync_at ? 'Most recent sync' : 'No runs yet'}
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  )
}
