import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ChevronDown, ChevronUp, AlertTriangle, Eye } from 'lucide-react'
import { usePreviewMapping } from '@/hooks/queries/useMappings'
import type { FieldMapping } from '@/types/api'

interface PreviewPanelProps {
  connectorId: string | undefined
  mappings: FieldMapping[]
  sampleData: any
}

export const PreviewPanel = ({ connectorId, mappings, sampleData }: PreviewPanelProps) => {
  const [isExpanded, setIsExpanded] = useState(true)
  const [previewData, setPreviewData] = useState<any>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const previewMutation = usePreviewMapping()

  // Debounced preview update
  useEffect(() => {
    if (!connectorId || mappings.length === 0) {
      setPreviewData(null)
      setWarnings([])
      return
    }

    const timer = setTimeout(() => {
      triggerPreview()
    }, 500)

    return () => clearTimeout(timer)
  }, [connectorId, mappings])

  const triggerPreview = async () => {
    if (!connectorId) return

    try {
      const result = await previewMutation.mutateAsync({ connectorId })
      setPreviewData(result.transformed)
      setWarnings(result.warnings || [])
    } catch (error) {
      console.error('Preview failed:', error)
      setWarnings(['Failed to generate preview'])
    }
  }

  // Check for validation warnings
  const requiredFields = ['name', 'netbiosName', 'address']
  const mappedTargets = new Set(mappings.map((m) => m.target_field))
  const hasRequiredField = requiredFields.some((field) => mappedTargets.has(field))

  const validationWarnings: string[] = []
  if (!hasRequiredField && mappings.length > 0) {
    validationWarnings.push(
      'At least one identity field (name, netbiosName, or address) must be mapped'
    )
  }

  const allWarnings = [...validationWarnings, ...warnings]

  return (
    <div className="border-t mt-4">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-accent/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">Preview Panel</h3>
          {allWarnings.length > 0 && (
            <div className="flex items-center gap-1 text-destructive">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-medium">{allWarnings.length} warnings</span>
            </div>
          )}
        </div>
        {isExpanded ? (
          <ChevronDown className="h-5 w-5" />
        ) : (
          <ChevronUp className="h-5 w-5" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          {allWarnings.length > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <div className="space-y-1">
                  {allWarnings.map((warning, i) => (
                    <div key={i}>• {warning}</div>
                  ))}
                </div>
              </AlertDescription>
            </Alert>
          )}

          {previewData && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Transformed Output</span>
                <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                  <DialogTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Eye className="h-4 w-4 mr-2" />
                      Preview Before/After
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-4xl max-h-[80vh]">
                    <DialogHeader>
                      <DialogTitle>Mapping Preview</DialogTitle>
                    </DialogHeader>
                    <div className="grid grid-cols-2 gap-4 overflow-auto">
                      <div>
                        <h4 className="text-sm font-semibold mb-2">Before (Source)</h4>
                        <pre className="text-xs p-3 bg-muted rounded-md overflow-auto">
                          {JSON.stringify(sampleData, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold mb-2">After (Transformed)</h4>
                        <pre className="text-xs p-3 bg-muted rounded-md overflow-auto">
                          {JSON.stringify(previewData, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
              <pre className="text-xs p-3 bg-muted rounded-md overflow-auto max-h-40">
                {JSON.stringify(previewData, null, 2)}
              </pre>
            </div>
          )}

          {!previewData && mappings.length === 0 && (
            <div className="text-sm text-muted-foreground text-center py-4">
              Add mappings to see live preview
            </div>
          )}

          {!previewData && mappings.length > 0 && previewMutation.isPending && (
            <div className="text-sm text-muted-foreground text-center py-4">
              Generating preview...
            </div>
          )}
        </div>
      )}
    </div>
  )
}
