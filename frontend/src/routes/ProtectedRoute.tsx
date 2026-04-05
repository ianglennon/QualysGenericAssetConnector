import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/providers/AuthProvider'
import { ROUTES } from './constants'
import type { ReactNode } from 'react'

interface ProtectedRouteProps {
  children: ReactNode
  requiredPermission?: string
  requiredPermissions?: string[]
}

export default function ProtectedRoute({ children, requiredPermission, requiredPermissions }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasPermission, mustChangePassword } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />
  }

  if (mustChangePassword && location.pathname !== ROUTES.PROFILE) {
    return <Navigate to={ROUTES.PROFILE} replace />
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to={ROUTES.DASHBOARD} replace />
  }

  if (requiredPermissions && requiredPermissions.length > 0) {
    const hasAny = requiredPermissions.some(p => hasPermission(p))
    if (!hasAny) {
      return <Navigate to={ROUTES.DASHBOARD} replace />
    }
  }

  return <>{children}</>
}
