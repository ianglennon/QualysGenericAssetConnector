import type { ConnectionLineComponentProps } from '@xyflow/react'

export function DashedConnectionLine({
  fromX,
  fromY,
  toX,
  toY,
}: ConnectionLineComponentProps) {
  return (
    <g>
      <path
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth={2}
        strokeDasharray="6 3"
        d={`M${fromX},${fromY} C${fromX + 80},${fromY} ${toX - 80},${toY} ${toX},${toY}`}
        style={{
          animation: 'dash 0.8s linear infinite',
        }}
      />
      <style>{`
        @keyframes dash {
          to { stroke-dashoffset: -18; }
        }
      `}</style>
    </g>
  )
}
