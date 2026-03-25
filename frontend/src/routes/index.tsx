import { createBrowserRouter, Outlet, Navigate } from 'react-router-dom'
import { ROUTES } from './constants'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import { ConnectorListPage } from '@/pages/Connectors/ConnectorListPage'
import { ConnectorDetailPage } from '@/pages/Connectors/ConnectorDetailPage'
import { EndpointMappingsPage } from '@/pages/Connectors/EndpointMappingsPage'
import { ChainCanvasPage } from '@/pages/Connectors/ChainCanvasPage'
import { QualysConfig } from '@/pages/Settings/QualysConfig'
import { TransformRules } from '@/pages/Settings/TransformRules'
import { UserProfile } from '@/pages/Settings/UserProfile'
import RunHistoryPage from '@/pages/RunHistory/RunHistoryPage'
import RunDetailPage from '@/pages/RunHistory/RunDetailPage'
import ProtectedRoute from './ProtectedRoute'
import { AuthProvider } from '@/providers/AuthProvider'
import { MainLayout } from '@/components/layout/MainLayout'

// Root layout that provides auth context
function RootLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
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
              <ProtectedRoute allowedRoles={['admin']}>
                <Outlet />
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
            ],
          },
        ],
      },
    ],
  },
])
