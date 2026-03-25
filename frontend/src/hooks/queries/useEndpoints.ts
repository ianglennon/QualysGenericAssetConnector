import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { ConnectorEndpoint, EndpointCreate } from '@/types/api'

export const useEndpoints = (
  connectorId: string | undefined,
  options?: { unassignedOnly?: boolean }
) => {
  const unassignedOnly = options?.unassignedOnly ?? false
  return useQuery({
    queryKey: ['endpoints', connectorId, { unassignedOnly }],
    queryFn: async () => {
      if (!connectorId) return []
      const params = unassignedOnly ? '?unassigned_only=true' : ''
      const { data } = await apiClient.get<ConnectorEndpoint[]>(
        `/connectors/${connectorId}/endpoints${params}`
      )
      return data
    },
    enabled: !!connectorId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export const useCreateEndpoint = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; endpoint: EndpointCreate }) => {
      const { data } = await apiClient.post<ConnectorEndpoint>(
        `/connectors/${params.connectorId}/endpoints`,
        params.endpoint
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['endpoints', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useUpdateEndpoint = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      connectorId: string
      endpointId: string
      endpoint: Partial<EndpointCreate>
    }) => {
      const { data } = await apiClient.patch<ConnectorEndpoint>(
        `/connectors/${params.connectorId}/endpoints/${params.endpointId}`,
        params.endpoint
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['endpoints', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useDeleteEndpoint = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; endpointId: string }) => {
      await apiClient.delete(
        `/connectors/${params.connectorId}/endpoints/${params.endpointId}`
      )
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['endpoints', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useReorderEndpoints = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; order: string[] }) => {
      const { data } = await apiClient.post<ConnectorEndpoint[]>(
        `/connectors/${params.connectorId}/endpoints/reorder`,
        { order: params.order }
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['endpoints', variables.connectorId] })
    },
  })
}
