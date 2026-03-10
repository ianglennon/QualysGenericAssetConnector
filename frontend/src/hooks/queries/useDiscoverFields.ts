import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { DiscoverResponse } from '@/types/canvas'

export const useDiscoverFields = (connectorId: string | undefined) => {
  return useQuery({
    queryKey: ['fields', 'discover', connectorId],
    queryFn: async () => {
      const { data } = await apiClient.get<DiscoverResponse>(
        `/connectors/${connectorId}/fields/discover`
      )
      return data
    },
    enabled: !!connectorId,
    staleTime: 1000 * 60 * 5, // 5 minutes — matches useMappings pattern
  })
}
