import { createBrowserRouter, Outlet, Navigate } from 'react-router-dom'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import { ConnectorListPage } from '@/pages/Connectors/ConnectorListPage'
import { ConnectorDetailPage } from '@/pages/Connectors/ConnectorDetailPage'
import Mappings from '@/pages/Settings/Mappings'
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
            element: <Navigate to="/dashboard" replace />,
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
            path: 'runs',
            element: <RunHistoryPage />,
          },
          {
            path: 'runs/:id',
            element: <RunDetailPage />,
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
                element: <Navigate to="/settings/mappings" replace />,
              },
              {
                path: 'mappings',
                element: <Mappings />,
              },
            ],
          },
        ],
      },
    ],
  },
])
