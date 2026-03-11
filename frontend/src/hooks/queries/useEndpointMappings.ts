import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { FieldMapping, FieldMappingCreate, BatchReplaceResponse } from '@/types/api'

export const useEndpointMappings = (
  connectorId: string | undefined,
  endpointId: string | undefined
) => {
  return useQuery({
    queryKey: ['mappings', connectorId, endpointId],
    queryFn: async () => {
      if (!connectorId || !endpointId) return []
      const { data } = await apiClient.get<FieldMapping[]>(
        `/connectors/${connectorId}/endpoints/${endpointId}/mappings`
      )
      return data
    },
    enabled: !!connectorId && !!endpointId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export const useBatchReplaceEndpointMappings = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      connectorId: string
      endpointId: string
      mappings: FieldMappingCreate[]
    }) => {
      const { data } = await apiClient.put<BatchReplaceResponse>(
        `/connectors/${params.connectorId}/endpoints/${params.endpointId}/mappings`,
        { mappings: params.mappings }
      )
      return data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['mappings', variables.connectorId, variables.endpointId],
      })
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })
}
