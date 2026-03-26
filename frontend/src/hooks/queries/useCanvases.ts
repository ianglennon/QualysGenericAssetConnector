import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { CanvasResponse, CanvasListItem, CanvasUpdate } from '@/types/canvas'

export const useCanvases = (connectorId: string | undefined) => {
  return useQuery({
    queryKey: ['canvases', connectorId],
    queryFn: async () => {
      if (!connectorId) return []
      const { data } = await apiClient.get<CanvasListItem[]>(
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

export const useUpdateCanvas = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: { connectorId: string; canvasId: string; payload: CanvasUpdate }) => {
      const { data } = await apiClient.patch<CanvasResponse>(
        `/connectors/${params.connectorId}/canvases/${params.canvasId}`,
        params.payload
      )
      return data
    },
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: ['canvases', variables.connectorId] })
      const previous = queryClient.getQueryData<CanvasListItem[]>(['canvases', variables.connectorId])
      queryClient.setQueryData<CanvasListItem[]>(['canvases', variables.connectorId], (old) =>
        old?.map(c => c.id === variables.canvasId ? { ...c, ...variables.payload } : c)
      )
      return { previous }
    },
    onError: (_err, variables, context) => {
      queryClient.setQueryData(['canvases', variables.connectorId], context?.previous)
    },
    onSettled: (_, __, variables) => {
      queryClient.invalidateQueries({ queryKey: ['canvases', variables.connectorId] })
    },
  })
}

export const useDeleteCanvas = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: { connectorId: string; canvasId: string }) => {
      await apiClient.delete(`/connectors/${params.connectorId}/canvases/${params.canvasId}`)
    },
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: ['canvases', variables.connectorId] })
      const previous = queryClient.getQueryData<CanvasListItem[]>(['canvases', variables.connectorId])
      queryClient.setQueryData<CanvasListItem[]>(
        ['canvases', variables.connectorId],
        (old) => old?.filter(c => c.id !== variables.canvasId)
      )
      return { previous }
    },
    onError: (_err, variables, context) => {
      queryClient.setQueryData(['canvases', variables.connectorId], context?.previous)
    },
    onSettled: (_, __, variables) => {
      queryClient.invalidateQueries({ queryKey: ['canvases', variables.connectorId] })
    },
  })
}

export const useTriggerCanvasSync = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: { connectorId: string; canvasId: string }) => {
      const { data } = await apiClient.post(
        `/connectors/${params.connectorId}/runs?canvas_id=${params.canvasId}`
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['canvases', variables.connectorId] })
    },
  })
}
