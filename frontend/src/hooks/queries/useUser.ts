import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { UserPreferences, PasswordChangeRequest, Session } from '@/types/api'

export const useUserPreferences = () => {
  return useQuery({
    queryKey: ['user', 'preferences'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<UserPreferences>('/users/me/preferences')
        return data
      } catch (error) {
        // Fallback to localStorage if backend doesn't support preferences yet
        const saved = localStorage.getItem('userPreferences')
        if (saved) {
          return JSON.parse(saved) as UserPreferences
        }
        return {
          theme: 'light' as const,
          font_size: 'normal' as const,
          reduced_motion: false,
        }
      }
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export const useUpdatePreferences = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (preferences: Partial<UserPreferences>) => {
      try {
        const { data } = await apiClient.patch<UserPreferences>('/users/me/preferences', preferences)
        return data
      } catch (error) {
        // Fallback to localStorage if backend doesn't support preferences yet
        const current = localStorage.getItem('userPreferences')
        const updated = { ...(current ? JSON.parse(current) : {}), ...preferences }
        localStorage.setItem('userPreferences', JSON.stringify(updated))
        return updated as UserPreferences
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'preferences'] })
    },
  })
}

export const useChangePassword = () => {
  return useMutation({
    mutationFn: async (payload: PasswordChangeRequest) => {
      const { data } = await apiClient.post('/auth/change-password', payload)
      return data
    },
  })
}

export const useSessions = () => {
  return useQuery({
    queryKey: ['user', 'sessions'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<Session[]>('/auth/sessions')
        return data
      } catch (error) {
        // Placeholder - endpoint doesn't exist yet
        return [] as Session[]
      }
    },
    enabled: false, // Disabled until endpoint exists
  })
}
