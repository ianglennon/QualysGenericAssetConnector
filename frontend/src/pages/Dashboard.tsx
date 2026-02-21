import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageContainer } from '@/components/layout/PageContainer'
import { useAuth } from '@/hooks/useAuth'
import { useConnectors } from '@/hooks/queries/useConnectors'

export default function Dashboard() {
  const { user } = useAuth()
  const { data: connectors = [] } = useConnectors()

  const isAdmin = user?.role === 'admin'

  return (
    <PageContainer
      title="Dashboard"
      actions={
        isAdmin ? (
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
              Role: <span className="capitalize font-medium">{user?.role}</span>
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
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">
                Placeholder (coming soon)
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">
                Placeholder (coming soon)
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Last Sync</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">-</div>
              <p className="text-xs text-muted-foreground">
                Placeholder (coming soon)
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  )
}
