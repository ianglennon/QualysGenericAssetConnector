import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { QualysSchemaResponse } from '@/types/canvas'

export const useQualysSchema = () => {
  return useQuery({
    queryKey: ['qualys', 'schema'],
    queryFn: async () => {
      const { data } = await apiClient.get<QualysSchemaResponse>('/qualys/schema')
      return data
    },
    staleTime: 1000 * 60 * 30, // 30 minutes — Qualys schema rarely changes
  })
}
