import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { ROUTES } from '@/routes/constants'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const settingsTabs = [
  { label: 'Qualys Config', path: ROUTES.SETTINGS_QUALYS, permission: 'settings:read' },
  { label: 'Transform Rules', path: ROUTES.SETTINGS_TRANSFORM_RULES, permission: 'settings:read' },
  { label: 'Users', path: ROUTES.SETTINGS_USERS, permission: 'users:read' },
  { label: 'Roles', path: ROUTES.SETTINGS_ROLES, permission: 'roles:read' },
]

export function SettingsTabBar() {
  const { hasPermission } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const visibleTabs = settingsTabs.filter(tab => hasPermission(tab.permission))

  // Determine active tab from current path (match by prefix for roles sub-routes like /settings/roles/:id)
  const activeTab = visibleTabs.find(tab =>
    location.pathname === tab.path || location.pathname.startsWith(tab.path + '/')
  )?.path ?? visibleTabs[0]?.path

  if (visibleTabs.length === 0) return null

  return (
    <div className="border-b mb-6">
      <Tabs value={activeTab} onValueChange={(value) => navigate(value)}>
        <TabsList>
          {visibleTabs.map(tab => (
            <TabsTrigger key={tab.path} value={tab.path}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  )
}
