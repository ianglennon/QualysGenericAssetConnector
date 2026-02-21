import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { RunHistory, RunHistoryList } from '@/types/api'

interface UseRunsParams {
  connector_id?: string
  status?: string
  date_from?: string
  date_to?: string
  cursor?: string
  page?: number
  size?: number
}

export const useRuns = (filters?: UseRunsParams) => {
  return useQuery({
    queryKey: ['runs', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters?.connector_id) params.append('connector_id', filters.connector_id)
      if (filters?.status) params.append('status', filters.status)
      if (filters?.date_from) params.append('date_from', filters.date_from)
      if (filters?.date_to) params.append('date_to', filters.date_to)
      if (filters?.cursor) params.append('cursor', filters.cursor)
      if (filters?.page) params.append('page', filters.page.toString())
      if (filters?.size) params.append('size', filters.size.toString())

      const { data } = await apiClient.get<RunHistoryList>(
        `/runs?${params.toString()}`
      )
      return data
    },
    staleTime: 1000 * 30, // 30 seconds (runs change frequently)
  })
}

export const useRun = (runId: string | undefined) => {
  return useQuery({
    queryKey: ['runs', runId],
    queryFn: async () => {
      if (!runId) return null
      const { data } = await apiClient.get<RunHistory>(`/runs/${runId}`)
      return data
    },
    enabled: !!runId,
    staleTime: 1000 * 60 * 5,
  })
}

export const useTriggerRun = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (connectorId: string) => {
      const { data } = await apiClient.post(`/connectors/${connectorId}/runs`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}
