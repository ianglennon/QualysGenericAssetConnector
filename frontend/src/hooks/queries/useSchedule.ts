import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface ScheduleResponse {
  interval_type: string | null
  interval_value: number | null
  schedule_enabled: boolean
  execution_timeout: number | null
  next_run_at: string | null
}

interface SaveScheduleInput {
  interval_type: string
  interval_value: number
}

export const useSaveSchedule = (connectorId: string) => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (input: SaveScheduleInput) => {
      const { data } = await apiClient.put<ScheduleResponse>(
        `/connectors/${connectorId}/schedule`,
        { interval: { interval_type: input.interval_type, interval_value: input.interval_value } }
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const usePauseSchedule = (connectorId: string) => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ScheduleResponse>(
        `/connectors/${connectorId}/schedule/pause`
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useResumeSchedule = (connectorId: string) => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<ScheduleResponse>(
        `/connectors/${connectorId}/schedule/resume`
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors', connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}
