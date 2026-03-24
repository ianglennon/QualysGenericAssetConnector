import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { CanvasEndpointResponse, CanvasEndpointCreate, CanvasEndpointUpdate } from '@/types/canvas'

export const useCanvasEndpoints = (connectorId: string | undefined, canvasId: string | undefined) => {
  return useQuery({
    queryKey: ['canvas-endpoints', connectorId, canvasId],
    queryFn: async () => {
      if (!connectorId || !canvasId) return []
      const { data } = await apiClient.get<CanvasEndpointResponse[]>(
        `/connectors/${connectorId}/canvases/${canvasId}/endpoints`
      )
      return data
    },
    enabled: !!connectorId && !!canvasId,
    staleTime: 1000 * 60 * 5,
  })
}

export const useCreateCanvasEndpoint = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: {
      connectorId: string
      canvasId: string
      payload: CanvasEndpointCreate
    }) => {
      const { data } = await apiClient.post<CanvasEndpointResponse>(
        `/connectors/${params.connectorId}/canvases/${params.canvasId}/endpoints`,
        params.payload
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['canvas-endpoints', variables.connectorId, variables.canvasId],
      })
    },
  })
}

export const useUpdateCanvasEndpoint = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: {
      connectorId: string
      canvasId: string
      canvasEndpointId: string
      payload: CanvasEndpointUpdate
    }) => {
      const { data } = await apiClient.patch<CanvasEndpointResponse>(
        `/connectors/${params.connectorId}/canvases/${params.canvasId}/endpoints/${params.canvasEndpointId}`,
        params.payload
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['canvas-endpoints', variables.connectorId, variables.canvasId],
      })
    },
  })
}

export const useDeleteCanvasEndpoint = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: {
      connectorId: string
      canvasId: string
      canvasEndpointId: string
    }) => {
      await apiClient.delete(
        `/connectors/${params.connectorId}/canvases/${params.canvasId}/endpoints/${params.canvasEndpointId}`
      )
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['canvas-endpoints', variables.connectorId, variables.canvasId],
      })
    },
  })
}
