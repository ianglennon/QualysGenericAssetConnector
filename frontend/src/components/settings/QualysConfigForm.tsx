import { useForm } from 'react-hook-form'
import { useQualysConfig, useUpdateQualysConfig } from '@/hooks/queries/useQualys'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from '@/hooks/use-toast'
import type { QualysConfigUpdate } from '@/types/api'

interface FormData {
  api_url: string
  username: string
  connector_uuid: string
  password: string
  token: string
}

export const QualysConfigForm = () => {
  const { data: config, isLoading } = useQualysConfig()
  const updateMutation = useUpdateQualysConfig()

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      api_url: config?.api_url || '',
      username: config?.username || '',
      connector_uuid: config?.connector_uuid || '',
      password: '',
      token: '',
    },
    values: config ? {
      api_url: config.api_url,
      username: config.username,
      connector_uuid: config.connector_uuid,
      password: '',
      token: '',
    } : undefined,
  })

  const onSubmit = (data: FormData) => {
    const payload: QualysConfigUpdate = {
      api_url: data.api_url,
      username: data.username,
      connector_uuid: data.connector_uuid,
    }

    // Only include password/token if provided
    if (data.password) {
      payload.password = data.password
    }
    if (data.token) {
      payload.token = data.token
    }

    updateMutation.mutate(payload, {
      onSuccess: () => {
        toast({
          title: 'Success',
          description: 'Qualys configuration saved successfully',
        })
      },
      onError: (error: any) => {
        toast({
          title: 'Error',
          description: error.response?.data?.detail?.error?.message || 'Failed to save configuration',
          variant: 'destructive',
        })
      },
    })
  }

  if (isLoading) {
    return <div>Loading...</div>
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Qualys CSAM Configuration</CardTitle>
        <CardDescription>
          Configure your Qualys subscription credentials. All credentials are encrypted and never displayed after saving.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="api_url">API Endpoint URL</Label>
            <Input
              id="api_url"
              type="url"
              {...register('api_url', {
                required: 'API endpoint is required',
                pattern: {
                  value: /^https?:\/\/.+/,
                  message: 'Must be a valid URL',
                },
              })}
              placeholder="https://qualysapi.qualys.com"
            />
            {errors.api_url && (
              <p className="text-sm text-red-500">{errors.api_url.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
              {...register('username', { required: 'Username is required' })}
              placeholder={config?.username ? 'Leave blank to keep existing' : 'Enter username'}
            />
            {errors.username && (
              <p className="text-sm text-red-500">{errors.username.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="connector_uuid">Connector UUID</Label>
            <Input
              id="connector_uuid"
              type="text"
              {...register('connector_uuid', { required: 'Connector UUID is required' })}
              placeholder="UUID from Qualys CSAM dashboard"
            />
            {errors.connector_uuid && (
              <p className="text-sm text-red-500">{errors.connector_uuid.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              {...register('password')}
              placeholder={config?.has_password ? 'Leave blank to keep existing' : 'Enter password'}
            />
            {config?.has_password && (
              <p className="text-sm text-gray-500">Current password is set (encrypted)</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="token">Bearer Token (Optional)</Label>
            <Input
              id="token"
              type="password"
              {...register('token')}
              placeholder={config?.has_token ? 'Leave blank to keep existing' : 'Enter token if using token auth'}
            />
            {config?.has_token && (
              <p className="text-sm text-gray-500">Current token is set (encrypted)</p>
            )}
          </div>

          {config && (
            <p className="text-sm text-gray-500">
              Last updated: {new Date(config.api_url ? Date.now() : 0).toLocaleString()}
            </p>
          )}

          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Save Configuration'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
