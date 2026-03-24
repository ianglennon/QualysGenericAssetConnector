import { Badge } from '@/components/ui/badge'

interface TemplateVariableHintProps {
  path: string
}

export function TemplateVariableHint({ path }: TemplateVariableHintProps) {
  const variables: string[] = []
  const regex = /\{([^}]+)\}/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(path)) !== null) {
    variables.push(match[1])
  }

  if (variables.length === 0) return null

  return (
    <div className="flex items-center gap-1 flex-wrap mt-1">
      <span className="text-xs text-muted-foreground">Variables:</span>
      {variables.map((v) => (
        <Badge key={v} variant="secondary" className="text-xs">
          {v}
        </Badge>
      ))}
    </div>
  )
}
