import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { useTestConnection } from '@/hooks/queries/useConnectors'
import type { ConnectorCreate, Connector, AuthMethod, PaginationStrategy } from '@/types/api'

const connectorSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  base_url: z.string().url('Invalid URL'),
  test_path: z.string().optional(),
  auth_method: z.enum(['bearer_token', 'basic_auth', 'api_key_header']),
  credentials: z.object({
    token: z.string().optional(),
    username: z.string().optional(),
    password: z.string().optional(),
    api_key_name: z.string().optional(),
    api_key: z.string().optional(),
  }).optional(),
  pagination_strategies: z.array(z.any()).default([]),
})

type ConnectorFormData = z.infer<typeof connectorSchema>

interface ConnectorWizardProps {
  connector?: Connector
  onSubmit: (data: ConnectorCreate) => Promise<void>
  isSubmitting?: boolean
}

const steps = ['basic', 'auth', 'pagination', 'review'] as const
type Step = typeof steps[number]

export function ConnectorWizard({ connector, onSubmit, isSubmitting = false }: ConnectorWizardProps) {
  const [currentStep, setCurrentStep] = useState<Step>('basic')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const testConnectionMutation = useTestConnection()

  const isEditing = !!connector

  const form = useForm<ConnectorFormData>({
    resolver: zodResolver(connectorSchema),
    defaultValues: connector ? {
      name: connector.name,
      base_url: connector.base_url,
      test_path: connector.test_path || '',
      auth_method: connector.auth_method,
      credentials: {},
      pagination_strategies: connector.pagination_strategies || [],
    } : {
      name: '',
      base_url: '',
      test_path: '',
      auth_method: 'bearer_token',
      credentials: {},
      pagination_strategies: [],
    },
    mode: 'onChange',
  })

  const authMethod = form.watch('auth_method')

  const canJumpToStep = (step: Step): boolean => {
    if (!isEditing) {
      const stepIndex = steps.indexOf(step)
      const currentIndex = steps.indexOf(currentStep)
      return stepIndex <= currentIndex
    }
    return true // Allow jumping to any step when editing
  }

  const handleTestConnection = async () => {
    if (!connector?.id) {
      setTestResult({ success: false, message: 'Save connector first to test connection' })
      return
    }

    setTestResult(null)
    try {
      const result = await testConnectionMutation.mutateAsync(connector.id)
      if (result.success) {
        setTestResult({ success: true, message: `Connection successful (Status: ${result.status_code})` })
      } else {
        setTestResult({ success: false, message: result.error || 'Connection failed' })
      }
    } catch (error: any) {
      setTestResult({ success: false, message: error.message || 'Connection test failed' })
    }
  }

  const handleSubmit = form.handleSubmit(async (data) => {
    await onSubmit(data as ConnectorCreate)
  })

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Tabs value={currentStep} onValueChange={(value) => setCurrentStep(value as Step)}>
        <TabsList className="grid w-full grid-cols-4">
          {steps.map((step, index) => (
            <TabsTrigger
              key={step}
              value={step}
              disabled={!canJumpToStep(step)}
              className="capitalize"
            >
              {index + 1}. {step.replace('_', ' ')}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Step 1: Basic Info */}
        <TabsContent value="basic" className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Connector Name *</Label>
            <Input
              id="name"
              {...form.register('name')}
              placeholder="My API Connector"
            />
            {form.formState.errors.name && (
              <p className="text-sm text-destructive">{form.formState.errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="base_url">Base URL *</Label>
            <Input
              id="base_url"
              {...form.register('base_url')}
              placeholder="https://api.example.com"
            />
            {form.formState.errors.base_url && (
              <p className="text-sm text-destructive">{form.formState.errors.base_url.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="test_path">Test Path (optional)</Label>
            <Input
              id="test_path"
              {...form.register('test_path')}
              placeholder="/health or /api/v1/test"
            />
            <p className="text-xs text-muted-foreground">
              Endpoint to test connectivity (leave empty to use base URL)
            </p>
          </div>

          <div className="flex justify-end">
            <Button type="button" onClick={() => setCurrentStep('auth')}>
              Next
            </Button>
          </div>
        </TabsContent>

        {/* Step 2: Authentication */}
        <TabsContent value="auth" className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="auth_method">Authentication Method *</Label>
            <Select
              value={authMethod}
              onValueChange={(value) => form.setValue('auth_method', value as AuthMethod)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="bearer_token">Bearer Token</SelectItem>
                <SelectItem value="basic_auth">Basic Auth</SelectItem>
                <SelectItem value="api_key_header">API Key Header</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {authMethod === 'bearer_token' && (
            <div className="space-y-2">
              <Label htmlFor="token">Bearer Token {connector ? '(leave empty to keep existing)' : '*'}</Label>
              <Input
                id="token"
                type="password"
                {...form.register('credentials.token')}
                placeholder="Enter bearer token"
              />
            </div>
          )}

          {authMethod === 'basic_auth' && (
            <>
              <div className="space-y-2">
                <Label htmlFor="username">Username {connector ? '(leave empty to keep existing)' : '*'}</Label>
                <Input
                  id="username"
                  {...form.register('credentials.username')}
                  placeholder="Enter username"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password {connector ? '(leave empty to keep existing)' : '*'}</Label>
                <Input
                  id="password"
                  type="password"
                  {...form.register('credentials.password')}
                  placeholder="Enter password"
                />
              </div>
            </>
          )}

          {authMethod === 'api_key_header' && (
            <>
              <div className="space-y-2">
                <Label htmlFor="api_key_name">Header Name *</Label>
                <Input
                  id="api_key_name"
                  {...form.register('credentials.api_key_name')}
                  placeholder="X-API-Key"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="api_key">API Key {connector ? '(leave empty to keep existing)' : '*'}</Label>
                <Input
                  id="api_key"
                  type="password"
                  {...form.register('credentials.api_key')}
                  placeholder="Enter API key"
                />
              </div>
            </>
          )}

          {connector && (
            <div className="space-y-2 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={handleTestConnection}
                disabled={testConnectionMutation.isPending}
              >
                {testConnectionMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Test Connection
              </Button>
              {testResult && (
                <div className="flex items-center gap-2 text-sm">
                  {testResult.success ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                  <span className={testResult.success ? 'text-green-600' : 'text-destructive'}>
                    {testResult.message}
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-between">
            <Button type="button" variant="outline" onClick={() => setCurrentStep('basic')}>
              Previous
            </Button>
            <Button type="button" onClick={() => setCurrentStep('pagination')}>
              Next
            </Button>
          </div>
        </TabsContent>

        {/* Step 3: Pagination */}
        <TabsContent value="pagination" className="space-y-4">
          <div className="rounded-lg border p-4">
            <h3 className="text-sm font-medium mb-2">Pagination Strategies</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Configure how the connector handles paginated API responses. Multiple strategies can be configured.
            </p>
            {(form.watch('pagination_strategies') || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No pagination strategies configured (single-page response)</p>
            ) : (
              <div className="space-y-2">
                {(form.watch('pagination_strategies') as PaginationStrategy[] || []).map((strategy, index) => (
                  <div key={index} className="flex items-center justify-between rounded border p-2">
                    <Badge variant="outline">{strategy.strategy_type}</Badge>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-between">
            <Button type="button" variant="outline" onClick={() => setCurrentStep('auth')}>
              Previous
            </Button>
            <Button type="button" onClick={() => setCurrentStep('review')}>
              Next
            </Button>
          </div>
        </TabsContent>

        {/* Step 4: Review */}
        <TabsContent value="review" className="space-y-4">
          <div className="rounded-lg border p-4 space-y-4">
            <h3 className="text-lg font-medium">Review Connector Configuration</h3>
            
            <div>
              <p className="text-sm font-medium text-muted-foreground">Name</p>
              <p className="text-sm">{form.watch('name')}</p>
            </div>

            <div>
              <p className="text-sm font-medium text-muted-foreground">Base URL</p>
              <p className="text-sm">{form.watch('base_url')}</p>
            </div>

            {form.watch('test_path') && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">Test Path</p>
                <p className="text-sm">{form.watch('test_path')}</p>
              </div>
            )}

            <div>
              <p className="text-sm font-medium text-muted-foreground">Authentication</p>
              <p className="text-sm capitalize">{form.watch('auth_method').replace('_', ' ')}</p>
            </div>

            <div>
              <p className="text-sm font-medium text-muted-foreground">Pagination</p>
              <p className="text-sm">
                {(form.watch('pagination_strategies') || []).length} strateg{(form.watch('pagination_strategies') || []).length === 1 ? 'y' : 'ies'} configured
              </p>
            </div>
          </div>

          <div className="flex justify-between">
            <Button type="button" variant="outline" onClick={() => setCurrentStep('pagination')}>
              Previous
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Update Connector' : 'Create Connector'}
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </form>
  )
}
