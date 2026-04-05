import { createBrowserRouter, Outlet, Navigate } from 'react-router-dom'
import { ROUTES } from './constants'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import { ConnectorListPage } from '@/pages/Connectors/ConnectorListPage'
import { ConnectorDetailPage } from '@/pages/Connectors/ConnectorDetailPage'
import { EndpointMappingsPage } from '@/pages/Connectors/EndpointMappingsPage'
import { ChainCanvasPage } from '@/pages/Connectors/ChainCanvasPage'
import { DryRunResultsPage } from '@/pages/Connectors/DryRunResultsPage'
import { QualysConfig } from '@/pages/Settings/QualysConfig'
import { TransformRules } from '@/pages/Settings/TransformRules'
import { UserProfile } from '@/pages/Settings/UserProfile'
import { UsersPage } from '@/pages/Settings/UsersPage'
import { RolesPage } from '@/pages/Settings/RolesPage'
import { RoleEditPage } from '@/pages/Settings/RoleEditPage'
import RunHistoryPage from '@/pages/RunHistory/RunHistoryPage'
import RunDetailPage from '@/pages/RunHistory/RunDetailPage'
import ProtectedRoute from './ProtectedRoute'
import { AuthProvider } from '@/providers/AuthProvider'
import { MainLayout } from '@/components/layout/MainLayout'
import { SettingsTabBar } from '@/components/layout/SettingsTabBar'

// Root layout that provides auth context
function RootLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

// Settings layout with tab navigation
function SettingsLayout() {
  return (
    <div>
      <SettingsTabBar />
      <Outlet />
    </div>
  )
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: '/login',
        element: <Login />,
      },
      {
        path: '/',
        element: (
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        ),
        children: [
          {
            index: true,
            element: <Navigate to={ROUTES.DASHBOARD} replace />,
          },
          {
            path: 'dashboard',
            element: <Dashboard />,
          },
          {
            path: 'connectors',
            element: <ConnectorListPage />,
          },
          {
            path: 'connectors/:id',
            element: <ConnectorDetailPage />,
          },
          {
            path: 'connectors/:connectorId/endpoints/:endpointId/mappings',
            element: <EndpointMappingsPage />,
          },
          {
            path: 'connectors/:connectorId/canvases/:canvasId',
            element: <ChainCanvasPage />,
          },
          {
            path: 'connectors/:connectorId/canvases/:canvasId/dry-run-results',
            element: <DryRunResultsPage />,
          },
          {
            path: 'runs',
            element: <RunHistoryPage />,
          },
          {
            path: 'runs/:id',
            element: <RunDetailPage />,
          },
          {
            path: 'profile',
            element: <UserProfile />,
          },
          {
            path: 'settings',
            element: (
              <ProtectedRoute requiredPermissions={['users:read', 'roles:read', 'settings:read']}>
                <SettingsLayout />
              </ProtectedRoute>
            ),
            children: [
              {
                index: true,
                element: <Navigate to={ROUTES.SETTINGS_QUALYS} replace />,
              },
              {
                path: 'qualys',
                element: <QualysConfig />,
              },
              {
                path: 'transform-rules',
                element: <TransformRules />,
              },
              {
                path: 'users',
                element: <UsersPage />,
              },
              {
                path: 'roles',
                element: <RolesPage />,
              },
              {
                path: 'roles/:roleId',
                element: <RoleEditPage />,
              },
            ],
          },
        ],
      },
    ],
  },
])
