import { Link } from 'react-router-dom'
import { ArrowLeft, Plus, LayoutGrid, Save, Loader2, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/routes/constants'

interface CanvasToolbarProps {
  onCreateEndpoint: () => void
  onAutoLayout: () => void
  onSave: () => void
  isSaving: boolean
  canSave: boolean
  connectorName: string
  connectorId: string
  // Phase 43: dry-run support (D-06)
  hasChain?: boolean
  onDryRun?: () => void
  isDryRunning?: boolean
}

export function CanvasToolbar({
  onCreateEndpoint,
  onAutoLayout,
  onSave,
  isSaving,
  canSave,
  connectorName,
  connectorId,
  hasChain,
  onDryRun,
  isDryRunning,
}: CanvasToolbarProps) {
  const saveDisabled = !canSave || isSaving

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b bg-background">
      {/* Left side: back link + breadcrumb */}
      <div className="flex items-center gap-2">
        <Link
          to={ROUTES.connectorDetail(connectorId)}
          className="text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <span className="text-sm">{connectorName}</span>
      </div>

      {/* Right side: action buttons */}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onCreateEndpoint}>
          <Plus className="h-4 w-4" />
          Create Endpoint
        </Button>
        <Button variant="outline" size="sm" onClick={onAutoLayout}>
          <LayoutGrid className="h-4 w-4" />
          Auto Layout
        </Button>
        {saveDisabled ? (
          <span title="Map at least one identity attribute to save">
            <Button variant="default" size="sm" disabled onClick={onSave}>
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save Canvas
            </Button>
          </span>
        ) : (
          <Button variant="default" size="sm" onClick={onSave}>
            <Save className="h-4 w-4" />
            Save Canvas
          </Button>
        )}
        {hasChain && onDryRun && (
          <Button
            variant="outline"
            size="sm"
            onClick={onDryRun}
            disabled={isDryRunning}
          >
            {isDryRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Dry Test
          </Button>
        )}
      </div>
    </div>
  )
}
