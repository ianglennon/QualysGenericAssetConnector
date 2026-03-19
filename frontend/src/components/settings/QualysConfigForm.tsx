import { useForm } from 'react-hook-form'
import { useQualysConfig, useUpdateQualysConfig } from '@/hooks/queries/useQualys'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from '@/hooks/use-toast'
import type { QualysConfigUpdate } from '@/types/api'

interface FormData {
  username: string
  password: string
  connector_uuid: string
}

export const QualysConfigForm = () => {
  const { data: config, isLoading } = useQualysConfig()
  const updateMutation = useUpdateQualysConfig()

  const { register, handleSubmit, setError, formState: { errors } } = useForm<FormData>({
    defaultValues: { username: '', password: '', connector_uuid: '' },
    values: config ? {
      username: config.username,
      connector_uuid: config.connector_uuid,
      password: '',
    } : undefined,
  })

  const onSubmit = (data: FormData) => {
    const payload: QualysConfigUpdate = {
      username: data.username,
      connector_uuid: data.connector_uuid,
    }
    if (data.password) {
      payload.password = data.password
    }

    updateMutation.mutate(payload, {
      onSuccess: () => {
        toast({
          title: 'Success',
          description: 'Qualys configuration saved successfully',
        })
      },
      onError: (error: any) => {
        const errorCode = error.response?.data?.error?.code
        const errorMessage = error.response?.data?.error?.message || 'Failed to save configuration'

        if (errorCode === 'QUALYS_INVALID_USERNAME') {
          setError('username', { message: errorMessage })
        }

        toast({
          title: 'Error',
          description: errorMessage,
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
          Configure your Qualys subscription credentials. Your password is encrypted at rest and never displayed after saving.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              type="text"
              {...register('username', { required: 'Username is required' })}
              placeholder="Enter Qualys username"
            />
            {errors.username && (
              <p className="text-sm text-destructive">{errors.username.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              {...register('password', {
                required: config?.has_password ? false : 'Password is required',
              })}
              placeholder={config?.has_password ? 'Leave blank to keep existing' : 'Enter password'}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
            {config?.has_password && (
              <p className="text-sm text-muted-foreground">Current password is set (encrypted)</p>
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
              <p className="text-sm text-destructive">{errors.connector_uuid.message}</p>
            )}
          </div>

          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Save Configuration'}
          </Button>
        </form>

        {config && (
          <div className="mt-6 rounded-lg border bg-muted/50 p-4 space-y-2">
            <p className="text-sm font-semibold">Detected Platform</p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-muted-foreground">Platform</dt>
              <dd>{config.platform_name}</dd>
              <dt className="text-muted-foreground">API Server</dt>
              <dd className="font-mono text-xs">{config.api_server_url}</dd>
              <dt className="text-muted-foreground">Gateway</dt>
              <dd className="font-mono text-xs">{config.api_gateway_url}</dd>
            </dl>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
