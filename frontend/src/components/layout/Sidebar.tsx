import { Link, useLocation } from 'react-router-dom'
import { Home, Database, History, Settings } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import { ROUTES } from '@/routes/constants'

const navigation: {
  name: string
  href: string
  icon: typeof Home
  permission?: string
  permissions?: string[]
}[] = [
  { name: 'Dashboard', href: ROUTES.DASHBOARD, icon: Home },
  { name: 'Connectors', href: ROUTES.CONNECTORS, icon: Database, permission: 'connectors:read' },
  { name: 'Run History', href: ROUTES.RUNS, icon: History, permission: 'runs:read' },
  { name: 'Settings', href: ROUTES.SETTINGS, icon: Settings, permissions: ['users:read', 'roles:read', 'settings:read'] },
]

export function Sidebar() {
  const location = useLocation()
  const { hasPermission, mustChangePassword } = useAuth()

  const allowedNavigation = navigation.filter(item => {
    if (!item.permission && !item.permissions) return true
    if (item.permission) return hasPermission(item.permission)
    if (item.permissions) return item.permissions.some(p => hasPermission(p))
    return false
  })

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r bg-background">
      <div className="flex h-full flex-col gap-y-5 overflow-y-auto px-6 py-4">
        {/* Logo/Brand */}
        <div className="flex h-16 shrink-0 items-center">
          <h1 className="text-xl font-bold">Qualys Connector</h1>
        </div>

        {/* Navigation */}
        <nav className="flex flex-1 flex-col">
          <ul role="list" className={cn('flex flex-1 flex-col gap-y-2', mustChangePassword && 'pointer-events-none opacity-50')}>
            {allowedNavigation.map((item) => {
              const isActive = location.pathname === item.href || location.pathname.startsWith(item.href + '/')
              return (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={cn(
                      'group flex gap-x-3 rounded-md p-2 text-sm font-medium leading-6 transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    <item.icon
                      className={cn(
                        'h-6 w-6 shrink-0',
                        isActive ? 'text-primary-foreground' : 'text-muted-foreground group-hover:text-accent-foreground'
                      )}
                      aria-hidden="true"
                    />
                    {item.name}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>
      </div>
    </aside>
  )
}
