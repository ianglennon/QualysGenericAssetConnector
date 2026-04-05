import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface UserResponse {
  id: string
  email: string
  is_active: boolean
  created_at: string
  role: { id: string; name: string }
}

export interface UserCreatePayload {
  email: string
  role_id: string
}

export interface UserCreateResponse {
  id: string
  email: string
  is_active: boolean
  must_change_password: boolean
  temporary_password: string
  role: { id: string; name: string }
}

export interface UserUpdatePayload {
  email?: string
  role_id?: string
  is_active?: boolean
}

export const useUsers = () => {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await apiClient.get<UserResponse[]>('/users')
      return data
    },
    staleTime: 1000 * 60 * 5,
  })
}

export const useCreateUser = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: UserCreatePayload) => {
      const { data } = await apiClient.post<UserCreateResponse>('/users', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export const useUpdateUser = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: UserUpdatePayload }) => {
      const { data } = await apiClient.patch<UserResponse>(`/users/${id}`, payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export const useDeactivateUser = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (userId: string) => {
      const { data } = await apiClient.post<UserResponse>(`/users/${userId}/deactivate`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
