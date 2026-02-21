import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { QualysConfig, QualysConfigUpdate } from '@/types/api'

export const useQualysConfig = () => {
  return useQuery({
    queryKey: ['qualys', 'config'],
    queryFn: async () => {
      const { data } = await apiClient.get<QualysConfig>('/qualys/config')
      return data
    },
    retry: false, // Don't retry if not configured
  })
}

export const useUpdateQualysConfig = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: QualysConfigUpdate) => {
      const { data } = await apiClient.put<QualysConfig>('/qualys/config', payload)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qualys', 'config'] })
    },
  })
}
