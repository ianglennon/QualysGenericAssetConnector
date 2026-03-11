import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { DiscoverResponse } from '@/types/canvas'

export const useEndpointDiscoverFields = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; endpointId: string }) => {
      const { data } = await apiClient.get<DiscoverResponse>(
        `/connectors/${params.connectorId}/endpoints/${params.endpointId}/fields/discover`
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['fields', 'discover', variables.connectorId, variables.endpointId],
      })
    },
  })
}
