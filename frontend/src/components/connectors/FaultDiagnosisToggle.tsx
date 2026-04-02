import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

interface FaultDiagnosisToggleProps {
  connectorId: string
  enabled: boolean
  onToggle: (enabled: boolean) => void
  isPending?: boolean
}

export function FaultDiagnosisToggle({ connectorId: _connectorId, enabled, onToggle, isPending }: FaultDiagnosisToggleProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-4">
      <div className="space-y-0.5">
        <Label htmlFor="fault-diagnosis" className="text-sm font-medium">
          Enable Fault Diagnosis
        </Label>
        <p className="text-sm text-muted-foreground">
          Captures detailed event logs for each pipeline stage during sync runs. Disable when not needed to reduce storage usage.
        </p>
      </div>
      <Switch
        id="fault-diagnosis"
        checked={enabled}
        onCheckedChange={onToggle}
        disabled={isPending}
      />
    </div>
  )
}
