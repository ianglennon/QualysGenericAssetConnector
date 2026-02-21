import { createBrowserRouter, Outlet } from 'react-router-dom'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Mappings from '@/pages/Settings/Mappings'
import ProtectedRoute from './ProtectedRoute'
import { AuthProvider } from '@/providers/AuthProvider'

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
        path: '/dashboard',
        element: (
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        ),
      },
      {
        path: '/',
        element: (
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        ),
      },
      {
        path: '/settings/mappings',
        element: (
          <ProtectedRoute allowedRoles={['admin']}>
            <Mappings />
          </ProtectedRoute>
        ),
      },
    ],
  },
])
