import { useMutation } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { DryRunResult } from '@/types/api'

export function useDryRun() {
  return useMutation({
    mutationFn: async ({ connectorId, canvasId }: { connectorId: string; canvasId: string }) => {
      const { data } = await apiClient.post<DryRunResult>(
        `/connectors/${connectorId}/canvases/${canvasId}/dry-run`
      )
      return data
    },
  })
}
