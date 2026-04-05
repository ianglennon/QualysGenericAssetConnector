import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient, setTokens, clearTokens, getAccessToken } from '@/lib/api-client'
import { ROUTES } from '@/routes/constants'
import type { User, LoginRequest, TokenResponse } from '@/types/auth'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  mustChangePassword: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasPermission: (permission: string) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  const hasPermission = (permission: string): boolean =>
    user?.role.permissions.includes(permission) ?? false

  const mustChangePassword = user?.must_change_password ?? false

  // On mount: if tokens exist in memory, validate by calling /api/v1/auth/me
  useEffect(() => {
    const validateSession = async () => {
      const token = getAccessToken()
      if (!token) {
        setIsLoading(false)
        return
      }

      try {
        const response = await apiClient.get<User>('/auth/me')
        setUser(response.data)
        if (response.data.must_change_password) {
          navigate(ROUTES.PROFILE)
        }
      } catch {
        clearTokens()
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    validateSession()
  }, [])

  const login = async (email: string, password: string) => {
    const payload: LoginRequest = { email, password }
    const response = await apiClient.post<TokenResponse>('/auth/login', payload)

    const { access_token, refresh_token } = response.data
    setTokens(access_token, refresh_token)

    // Fetch user details
    const userResponse = await apiClient.get<User>('/auth/me')
    setUser(userResponse.data)

    if (userResponse.data.must_change_password) {
      navigate(ROUTES.PROFILE)
      return
    }
  }

  const logout = () => {
    clearTokens()
    setUser(null)
    navigate(ROUTES.LOGIN)
  }

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    mustChangePassword,
    login,
    logout,
    hasPermission,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
