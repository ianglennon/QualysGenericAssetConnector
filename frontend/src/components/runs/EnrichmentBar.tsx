interface EnrichmentBarProps {
  full: number
  partial: number
  baseOnly: number
}

export function EnrichmentBar({ full, partial, baseOnly }: EnrichmentBarProps) {
  const total = full + partial + baseOnly
  if (total === 0) return null

  const pctFull = (full / total) * 100
  const pctPartial = (partial / total) * 100
  const pctBaseOnly = (baseOnly / total) * 100

  return (
    <div className="space-y-1">
      <div className="flex h-3 rounded-full overflow-hidden">
        {pctFull > 0 && (
          <div
            className="bg-green-600"
            style={{ width: `${pctFull}%` }}
            title={`Full: ${full}`}
          />
        )}
        {pctPartial > 0 && (
          <div
            className="bg-yellow-500"
            style={{ width: `${pctPartial}%` }}
            title={`Partial: ${partial}`}
          />
        )}
        {pctBaseOnly > 0 && (
          <div
            className="bg-gray-400 dark:bg-gray-500"
            style={{ width: `${pctBaseOnly}%` }}
            title={`Base Only: ${baseOnly}`}
          />
        )}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{full} full</span>
        <span>{partial} partial</span>
        <span>{baseOnly} base only</span>
      </div>
    </div>
  )
}
