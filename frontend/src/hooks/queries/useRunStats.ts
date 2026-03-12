import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { RunStats } from '@/types/api'

export const useRunStats = () => {
  return useQuery({
    queryKey: ['runStats'],
    queryFn: async () => {
      const { data } = await apiClient.get<RunStats>('/runs/stats')
      return data
    },
    staleTime: 1000 * 30, // 30 seconds
  })
}
