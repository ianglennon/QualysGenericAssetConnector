import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { FieldMapping, FieldMappingCreate, PreviewResponse, BatchReplaceResponse } from '@/types/api'

export const useMappings = (connectorId: string | undefined) => {
  return useQuery({
    queryKey: ['mappings', connectorId],
    queryFn: async () => {
      if (!connectorId) return []
      const { data } = await apiClient.get<FieldMapping[]>(
        `/connectors/${connectorId}/mappings`
      )
      return data
    },
    enabled: !!connectorId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export const useCreateMapping = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; mapping: FieldMappingCreate }) => {
      const { data } = await apiClient.post<FieldMapping>(
        `/connectors/${params.connectorId}/mappings`,
        params.mapping
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['mappings', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useUpdateMapping = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      connectorId: string
      mappingId: string
      mapping: FieldMappingCreate
    }) => {
      const { data } = await apiClient.patch<FieldMapping>(
        `/connectors/${params.connectorId}/mappings/${params.mappingId}`,
        params.mapping
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['mappings', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useDeleteMapping = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; mappingId: string }) => {
      await apiClient.delete(
        `/connectors/${params.connectorId}/mappings/${params.mappingId}`
      )
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['mappings', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const useBatchReplaceMappings = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { connectorId: string; mappings: FieldMappingCreate[] }) => {
      const { data } = await apiClient.put<BatchReplaceResponse>(
        `/connectors/${params.connectorId}/mappings`,
        { mappings: params.mappings }
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['mappings', variables.connectorId] })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}

export const usePreviewMapping = () => {
  return useMutation({
    mutationFn: async (params: { connectorId: string }) => {
      const { data } = await apiClient.post<PreviewResponse>(
        `/connectors/${params.connectorId}/mappings/preview`
      )
      return data
    },
  })
}

export const useLoadSourceFields = () => {
  return useMutation({
    mutationFn: async (connectorId: string) => {
      const { data } = await apiClient.post(`/connectors/${connectorId}/test`)
      return data
    },
  })
}
