import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { RunEventsResponse } from '@/types/api'

export const useRunEvents = (runId: string | undefined) => {
  return useQuery({
    queryKey: ['runEvents', runId],
    queryFn: async () => {
      if (!runId) return null
      const { data } = await apiClient.get<RunEventsResponse>(`/runs/${runId}/events`)
      return data
    },
    enabled: !!runId,
    staleTime: 1000 * 60 * 5,
  })
}
