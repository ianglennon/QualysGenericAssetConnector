import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { Connector, ConnectorCreate, TestConnectionResponse } from '@/types/api'

export const useConnectors = () => {
  return useQuery({
    queryKey: ['connectors'],
    queryFn: async () => {
      const { data } = await apiClient.get<Connector[]>('/connectors')
      return data
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export const useConnector = (connectorId: string | undefined) => {
  return useQuery({
    queryKey: ['connectors', connectorId],
    queryFn: async () => {
      if (!connectorId) return null
      const { data } = await apiClient.get<Connector>(`/connectors/${connectorId}`)
      return data
    },
    enabled: !!connectorId,
    staleTime: 1000 * 60 * 5,
  })
}

export const useCreateConnector = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (connector: ConnectorCreate) => {
      const { data } = await apiClient.post<Connector>('/connectors', connector)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useUpdateConnector = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, connector }: { id: string; connector: Partial<ConnectorCreate> }) => {
      const { data } = await apiClient.patch<Connector>(`/connectors/${id}`, connector)
      return data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
      queryClient.invalidateQueries({ queryKey: ['connectors', data.id] })
    },
  })
}

export const useDeleteConnector = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (connectorId: string) => {
      await apiClient.delete(`/connectors/${connectorId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useTestConnection = () => {
  return useMutation({
    mutationFn: async (connectorId: string) => {
      const { data } = await apiClient.post<TestConnectionResponse>(`/connectors/${connectorId}/test`)
      return data
    },
  })
}
