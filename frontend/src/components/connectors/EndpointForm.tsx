import { useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCreateEndpoint, useUpdateEndpoint } from '@/hooks/queries/useEndpoints'
import { useToast } from '@/hooks/use-toast'
import type { ConnectorEndpoint } from '@/types/api'

const endpointSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  path: z.string().min(1, 'Path is required').startsWith('/', 'Path must start with /'),
  pagination_strategy: z.enum(['none', 'cursor', 'offset', 'page_number', 'link_header']).default('none'),
  // Cursor fields
  cursor_param: z.string().optional(),
  next_cursor_path: z.string().optional(),
  cursor_page_size_param: z.string().optional(),
  // Offset fields
  limit_param: z.string().optional(),
  offset_param: z.string().optional(),
  // Page number fields
  page_param: z.string().optional(),
  page_size_param: z.string().optional(),
  // Link header fields
  link_page_size_param: z.string().optional(),
})

type EndpointFormValues = z.infer<typeof endpointSchema>

interface EndpointFormProps {
  connectorId: string
  endpoint?: ConnectorEndpoint
  open: boolean
  onOpenChange: (open: boolean) => void
}

function buildPaginationConfig(
  values: EndpointFormValues
): Record<string, unknown> | null {
  if (values.pagination_strategy === 'none') return null

  if (values.pagination_strategy === 'cursor') {
    return {
      strategy_type: 'cursor',
      cursor_param: values.cursor_param || '',
      next_cursor_path: values.next_cursor_path || '',
      ...(values.cursor_page_size_param
        ? { page_size_param: values.cursor_page_size_param }
        : {}),
    }
  }

  if (values.pagination_strategy === 'offset') {
    return {
      strategy_type: 'offset',
      limit_param: values.limit_param || '',
      offset_param: values.offset_param || '',
    }
  }

  if (values.pagination_strategy === 'page_number') {
    return {
      strategy_type: 'page_number',
      page_param: values.page_param || '',
      ...(values.page_size_param
        ? { page_size_param: values.page_size_param }
        : {}),
    }
  }

  if (values.pagination_strategy === 'link_header') {
    return {
      strategy_type: 'link_header',
      ...(values.link_page_size_param
        ? { page_size_param: values.link_page_size_param }
        : {}),
    }
  }

  return null
}

function getStrategyFromConfig(
  config: Record<string, unknown> | null
): EndpointFormValues['pagination_strategy'] {
  if (!config) return 'none'
  const strategyType = config.strategy_type as string
  if (strategyType === 'cursor') return 'cursor'
  if (strategyType === 'offset') return 'offset'
  if (strategyType === 'page_number') return 'page_number'
  if (strategyType === 'link_header') return 'link_header'
  return 'none'
}

export function EndpointForm({ connectorId, endpoint, open, onOpenChange }: EndpointFormProps) {
  const isEdit = !!endpoint
  const { toast } = useToast()
  const createEndpoint = useCreateEndpoint()
  const updateEndpoint = useUpdateEndpoint()

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    formState: { errors },
  } = useForm<EndpointFormValues>({
    resolver: zodResolver(endpointSchema),
    defaultValues: {
      name: '',
      path: '',
      pagination_strategy: 'none',
    },
  })

  // Populate form when editing
  useEffect(() => {
    if (open && endpoint) {
      const strategy = getStrategyFromConfig(endpoint.pagination_config)
      const config = endpoint.pagination_config || {}
      reset({
        name: endpoint.name,
        path: endpoint.path,
        pagination_strategy: strategy,
        cursor_param: config.cursor_param as string | undefined,
        next_cursor_path: config.next_cursor_path as string | undefined,
        cursor_page_size_param:
          strategy === 'cursor' ? (config.page_size_param as string | undefined) : undefined,
        limit_param: config.limit_param as string | undefined,
        offset_param: config.offset_param as string | undefined,
        page_param: config.page_param as string | undefined,
        page_size_param:
          strategy === 'page_number' ? (config.page_size_param as string | undefined) : undefined,
        link_page_size_param:
          strategy === 'link_header' ? (config.page_size_param as string | undefined) : undefined,
      })
    } else if (open && !endpoint) {
      reset({
        name: '',
        path: '',
        pagination_strategy: 'none',
      })
    }
  }, [open, endpoint, reset])

  const paginationStrategy = watch('pagination_strategy')

  const onSubmit = (values: EndpointFormValues) => {
    const pagination_config = buildPaginationConfig(values)
    const payload = {
      name: values.name,
      path: values.path,
      pagination_config: pagination_config ?? undefined,
    }

    if (isEdit && endpoint) {
      updateEndpoint.mutate(
        { connectorId, endpointId: endpoint.id, endpoint: payload },
        {
          onSuccess: () => onOpenChange(false),
          onError: () =>
            toast({ title: 'Failed to update endpoint', variant: 'destructive' }),
        }
      )
    } else {
      createEndpoint.mutate(
        { connectorId, endpoint: payload },
        {
          onSuccess: () => onOpenChange(false),
          onError: () =>
            toast({ title: 'Failed to create endpoint', variant: 'destructive' }),
        }
      )
    }
  }

  const isPending = createEndpoint.isPending || updateEndpoint.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Endpoint' : 'Add Endpoint'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Name */}
          <div className="space-y-1">
            <Label htmlFor="ep-name">Name</Label>
            <Input
              id="ep-name"
              placeholder="Servers"
              {...register('name')}
              aria-invalid={!!errors.name}
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          {/* Path */}
          <div className="space-y-1">
            <Label htmlFor="ep-path">Path</Label>
            <Input
              id="ep-path"
              placeholder="/api/servers"
              {...register('path')}
              aria-invalid={!!errors.path}
            />
            {errors.path && (
              <p className="text-xs text-destructive">{errors.path.message}</p>
            )}
          </div>

          {/* Pagination strategy */}
          <div className="space-y-1">
            <Label htmlFor="ep-pagination">Pagination Strategy</Label>
            <Controller
              name="pagination_strategy"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger id="ep-pagination">
                    <SelectValue placeholder="Select strategy" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None (single page)</SelectItem>
                    <SelectItem value="cursor">Cursor</SelectItem>
                    <SelectItem value="offset">Offset</SelectItem>
                    <SelectItem value="page_number">Page Number</SelectItem>
                    <SelectItem value="link_header">Link Header</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {/* Dynamic pagination fields */}
          {paginationStrategy === 'cursor' && (
            <div className="space-y-3 rounded-md border p-3">
              <div className="space-y-1">
                <Label htmlFor="ep-cursor-param">Cursor Param</Label>
                <Input id="ep-cursor-param" placeholder="cursor" {...register('cursor_param')} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="ep-next-cursor">Next Cursor Path</Label>
                <Input
                  id="ep-next-cursor"
                  placeholder="meta.next_cursor"
                  {...register('next_cursor_path')}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="ep-cursor-page-size">Page Size Param (optional)</Label>
                <Input
                  id="ep-cursor-page-size"
                  placeholder="per_page"
                  {...register('cursor_page_size_param')}
                />
              </div>
            </div>
          )}

          {paginationStrategy === 'offset' && (
            <div className="space-y-3 rounded-md border p-3">
              <div className="space-y-1">
                <Label htmlFor="ep-limit-param">Limit Param</Label>
                <Input id="ep-limit-param" placeholder="limit" {...register('limit_param')} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="ep-offset-param">Offset Param</Label>
                <Input id="ep-offset-param" placeholder="offset" {...register('offset_param')} />
              </div>
            </div>
          )}

          {paginationStrategy === 'page_number' && (
            <div className="space-y-3 rounded-md border p-3">
              <div className="space-y-1">
                <Label htmlFor="ep-page-param">Page Param</Label>
                <Input id="ep-page-param" placeholder="page" {...register('page_param')} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="ep-page-size-param">Page Size Param (optional)</Label>
                <Input
                  id="ep-page-size-param"
                  placeholder="per_page"
                  {...register('page_size_param')}
                />
              </div>
            </div>
          )}

          {paginationStrategy === 'link_header' && (
            <div className="space-y-3 rounded-md border p-3">
              <div className="space-y-1">
                <Label htmlFor="ep-link-page-size">Page Size Param (optional)</Label>
                <Input
                  id="ep-link-page-size"
                  placeholder="per_page"
                  {...register('link_page_size_param')}
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Saving...' : isEdit ? 'Save Changes' : 'Add Endpoint'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
