import { useState } from 'react'
import { ChevronRight, ChevronDown, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { HttpRequestDetail, HttpResponseDetail } from '@/types/api'

interface HttpDetailPanelProps {
  httpRequest?: HttpRequestDetail | null
  httpResponse?: HttpResponseDetail | null
}

function formatBody(body: string | null | undefined): string {
  if (!body) return ''
  try {
    const parsed = JSON.parse(body)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return body
  }
}

function serializeRequest(req: HttpRequestDetail): string {
  const lines: string[] = []
  lines.push(`${req.method} ${req.url}`)
  if (req.headers) {
    Object.entries(req.headers).forEach(([k, v]) => lines.push(`${k}: ${v}`))
  }
  if (req.body) {
    lines.push('')
    lines.push(formatBody(req.body))
  }
  return lines.join('\n')
}

function serializeResponse(res: HttpResponseDetail): string {
  const lines: string[] = []
  lines.push(`Status: ${res.status_code}`)
  if (res.headers) {
    Object.entries(res.headers).forEach(([k, v]) => lines.push(`${k}: ${v}`))
  }
  if (res.body) {
    lines.push('')
    lines.push(formatBody(res.body))
  }
  return lines.join('\n')
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Silent fail -- clipboard API may be unavailable
    }
  }

  return (
    <Button variant="ghost" size="icon" onClick={handleCopy} title="Copy to clipboard">
      {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
    </Button>
  )
}

function HeadersList({ headers }: { headers: Record<string, string> }) {
  return (
    <div className="font-mono text-xs space-y-0.5">
      {Object.entries(headers).map(([key, value]) => (
        <div key={key}>
          <span className="text-muted-foreground">{key}:</span> {value}
        </div>
      ))}
    </div>
  )
}

export function HttpDetailPanel({ httpRequest, httpResponse }: HttpDetailPanelProps) {
  const [isOpen, setIsOpen] = useState(false)

  const hasHttpDetails = httpRequest || httpResponse
  if (!hasHttpDetails) return null

  return (
    <div>
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
      >
        {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        HTTP Details
      </button>
      {isOpen && (
        <div className="space-y-4 mt-3">
          {httpRequest && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold">Request</h4>
                <CopyButton text={serializeRequest(httpRequest)} />
              </div>
              <div className="font-mono text-xs">{httpRequest.method} {httpRequest.url}</div>
              <HeadersList headers={httpRequest.headers} />
              {httpRequest.body && (
                <pre className="text-xs font-mono bg-muted p-4 rounded-md max-h-96 overflow-y-auto overflow-x-auto whitespace-pre-wrap">
                  {formatBody(httpRequest.body)}
                </pre>
              )}
            </div>
          )}
          {httpRequest && httpResponse && <Separator />}
          {httpResponse && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold">Response</h4>
                <CopyButton text={serializeResponse(httpResponse)} />
              </div>
              <div className="font-mono text-xs">Status: {httpResponse.status_code}</div>
              <HeadersList headers={httpResponse.headers} />
              {httpResponse.body && (
                <pre className="text-xs font-mono bg-muted p-4 rounded-md max-h-96 overflow-y-auto overflow-x-auto whitespace-pre-wrap">
                  {formatBody(httpResponse.body)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
