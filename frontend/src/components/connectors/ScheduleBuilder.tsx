import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/use-toast'
import { useSaveSchedule, usePauseSchedule, useResumeSchedule } from '@/hooks/queries/useSchedule'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { FireTimePreview } from './FireTimePreview'
import type { Connector } from '@/types/api'

interface ScheduleBuilderProps {
  connectorId: string
  connector: Connector
}

const INTERVAL_CONSTRAINTS: Record<string, { min: number; max: number; label: string }> = {
  minutes: { min: 5, max: 1440, label: 'Minutes' },
  hours: { min: 1, max: 168, label: 'Hours' },
  days: { min: 1, max: 365, label: 'Days' },
  weeks: { min: 1, max: 52, label: 'Weeks' },
}

function validateInterval(type: string, value: number): string | null {
  const c = INTERVAL_CONSTRAINTS[type]
  if (!c) return null
  if (isNaN(value)) return `${c.label} must be a number`
  if (value < c.min || value > c.max) {
    return `${c.label} must be between ${c.min.toLocaleString()} and ${c.max.toLocaleString()}`
  }
  return null
}

export function ScheduleBuilder({ connectorId, connector }: ScheduleBuilderProps) {
  const { hasPermission } = useAuth()
  const { toast } = useToast()

  const saveMutation = useSaveSchedule(connectorId)
  const pauseMutation = usePauseSchedule(connectorId)
  const resumeMutation = useResumeSchedule(connectorId)

  const [localType, setLocalType] = useState(connector.interval_type ?? 'hours')
  const [localValue, setLocalValue] = useState(connector.interval_value?.toString() ?? '')
  const [validationError, setValidationError] = useState<string | null>(null)

  // Sync local state with server after mutation invalidation
  useEffect(() => {
    setLocalType(connector.interval_type ?? 'hours')
    setLocalValue(connector.interval_value?.toString() ?? '')
  }, [connector.interval_type, connector.interval_value])

  // Validate on input change
  useEffect(() => {
    if (!localValue) {
      setValidationError(null)
      return
    }
    const parsed = parseInt(localValue, 10)
    setValidationError(validateInterval(localType, parsed))
  }, [localType, localValue])

  // Permission gate (after all hooks per rules-of-hooks)
  if (!hasPermission('schedules:read')) return null

  const canEdit = hasPermission('schedules:update')

  const handleToggle = async () => {
    try {
      if (connector.schedule_enabled) {
        await pauseMutation.mutateAsync()
      } else {
        await resumeMutation.mutateAsync()
      }
    } catch {
      toast({
        title: 'Failed to update schedule',
        description: 'Could not pause/resume the schedule. Try again.',
        variant: 'destructive',
      })
    }
  }

  const handleValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalValue(e.target.value)
  }

  const handleTypeChange = (value: string) => {
    setLocalType(value)
  }

  const handleSave = async () => {
    try {
      await saveMutation.mutateAsync({
        interval_type: localType,
        interval_value: parseInt(localValue, 10),
      })
      toast({ title: 'Schedule saved' })
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: { error_message?: string } } } }
      const description = axiosError.response?.data?.detail?.error_message ?? 'An unexpected error occurred'
      toast({
        title: 'Failed to save schedule',
        description,
        variant: 'destructive',
      })
    }
  }

  const isPaused = connector.schedule_enabled === false && !!connector.interval_type
  const parsedValue = parseInt(localValue, 10)
  const showFireTimes = !isPaused && !isNaN(parsedValue) && parsedValue > 0 && !validationError
  const isUnchanged = localType === connector.interval_type && parseInt(localValue, 10) === connector.interval_value
  const saveDisabled = saveMutation.isPending || validationError !== null || !localValue || isUnchanged || isPaused

  return (
    <div className="rounded-lg border p-6 space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Schedule</h3>
        <div className="flex items-center gap-2">
          <Label htmlFor="schedule-enabled" className="text-sm">Schedule Enabled</Label>
          <Switch
            id="schedule-enabled"
            checked={connector.schedule_enabled}
            onCheckedChange={handleToggle}
            disabled={!canEdit || !connector.interval_type || pauseMutation.isPending || resumeMutation.isPending}
            aria-label="Enable or disable automatic schedule"
          />
        </div>
      </div>

      {/* Interval picker row */}
      <div className={isPaused ? 'opacity-50' : ''}>
        <Label className="text-sm">Run every</Label>
        <div className="flex items-center gap-2 mt-1">
          <Input
            type="number"
            className="w-24"
            value={localValue}
            onChange={handleValueChange}
            min={INTERVAL_CONSTRAINTS[localType]?.min}
            max={INTERVAL_CONSTRAINTS[localType]?.max}
            disabled={!canEdit || isPaused}
            placeholder="Value"
            aria-describedby={validationError ? 'interval-error' : undefined}
          />
          <Select value={localType} onValueChange={handleTypeChange} disabled={!canEdit || isPaused}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="minutes">Minutes</SelectItem>
              <SelectItem value="hours">Hours</SelectItem>
              <SelectItem value="days">Days</SelectItem>
              <SelectItem value="weeks">Weeks</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Validation error */}
      {validationError && (
        <p id="interval-error" className="text-sm text-destructive">{validationError}</p>
      )}

      {/* Fire time preview */}
      {showFireTimes && <FireTimePreview intervalType={localType} intervalValue={parsedValue} />}

      {/* Empty state */}
      {!connector.interval_type && !localValue && (
        <div className="text-sm text-muted-foreground">
          <p className="font-medium">No schedule configured</p>
          <p>Set an interval above to schedule automatic syncs for this connector.</p>
        </div>
      )}

      {/* Save button */}
      {canEdit && (
        <Button onClick={handleSave} disabled={saveDisabled}>
          Save Schedule
        </Button>
      )}
    </div>
  )
}
