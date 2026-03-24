import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { CanvasResponse } from '@/types/canvas'

export const useCanvases = (connectorId: string | undefined) => {
  return useQuery({
    queryKey: ['canvases', connectorId],
    queryFn: async () => {
      if (!connectorId) return []
      const { data } = await apiClient.get<CanvasResponse[]>(
        `/connectors/${connectorId}/canvases`
      )
      return data
    },
    enabled: !!connectorId,
    staleTime: 1000 * 60 * 5,
  })
}

export const useCreateCanvas = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: { connectorId: string; name: string; description?: string }) => {
      const { data } = await apiClient.post<CanvasResponse>(
        `/connectors/${params.connectorId}/canvases`,
        { name: params.name, description: params.description }
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['canvases', variables.connectorId] })
    },
  })
}
