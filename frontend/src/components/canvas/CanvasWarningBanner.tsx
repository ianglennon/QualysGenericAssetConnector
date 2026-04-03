import { AlertTriangle } from 'lucide-react'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { IDENTITY_FIELDS } from '@/constants/canvas'

interface CanvasWarningBannerProps {
  visible: boolean
}

export function CanvasWarningBanner({ visible }: CanvasWarningBannerProps) {
  if (!visible) return null

  const fieldList = [...IDENTITY_FIELDS].sort().join(', ')

  return (
    <div className="absolute top-3 left-3 right-3 z-10 pointer-events-auto">
      <Alert className="border-yellow-500/50 bg-yellow-50 dark:bg-yellow-950/20">
        <AlertTriangle className="h-4 w-4 text-yellow-700 dark:text-yellow-400" />
        <AlertTitle className="font-semibold text-yellow-700 dark:text-yellow-400">
          No base endpoint detected
        </AlertTitle>
        <AlertDescription className="text-muted-foreground">
          Map at least one identity field to enable submission: {fieldList}
        </AlertDescription>
      </Alert>
    </div>
  )
}
