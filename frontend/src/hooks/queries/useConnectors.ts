import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { Connector } from '@/types/api'

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
      const { data} = await apiClient.get<Connector>(`/connectors/${connectorId}`)
      return data
    },
    enabled: !!connectorId,
    staleTime: 1000 * 60 * 5,
  })
}
