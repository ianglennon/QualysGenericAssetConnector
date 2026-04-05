import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export interface RoleListResponse {
  id: string
  name: string
  description: string | null
  is_system: boolean
  created_at: string
  user_count: number
}

export interface RolePermissionResponse {
  id: string
  name: string
  description: string | null
  is_system: boolean
  created_at: string
  permissions: string[]
}

export interface RoleCreatePayload {
  name: string
  description?: string
}

export interface RoleUpdatePayload {
  name?: string
  description?: string
}

export interface PermissionAddPayload {
  permissions: string[]
}

export const useRoles = () => {
  return useQuery({
    queryKey: ['roles'],
    queryFn: async () => {
      const { data } = await apiClient.get<RoleListResponse[]>('/roles')
      return data
    },
    staleTime: 1000 * 60 * 5,
  })
}

export const useRole = (roleId: string) => {
  return useQuery({
    queryKey: ['roles', roleId],
    queryFn: async () => {
      const { data } = await apiClient.get<RolePermissionResponse>(`/roles/${roleId}`)
      return data
    },
    enabled: !!roleId,
    staleTime: 1000 * 60 * 5,
  })
}

export const useCreateRole = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: RoleCreatePayload) => {
      const { data } = await apiClient.post<RolePermissionResponse>('/roles', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
    },
  })
}

export const useUpdateRole = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: RoleUpdatePayload }) => {
      const { data } = await apiClient.patch<RolePermissionResponse>(`/roles/${id}`, payload)
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      queryClient.invalidateQueries({ queryKey: ['roles', variables.id] })
    },
  })
}

export const useDeleteRole = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (roleId: string) => {
      await apiClient.delete(`/roles/${roleId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
    },
  })
}

export const useAddPermission = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ roleId, permissions }: { roleId: string; permissions: string[] }) => {
      const { data } = await apiClient.post<RolePermissionResponse>(
        `/roles/${roleId}/permissions`,
        { permissions }
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['roles', variables.roleId] })
    },
  })
}

export const useRemovePermission = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ roleId, permission }: { roleId: string; permission: string }) => {
      const { data } = await apiClient.delete<RolePermissionResponse>(
        `/roles/${roleId}/permissions/${permission}`
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['roles', variables.roleId] })
    },
  })
}
