import type { ReactNode } from 'react'

interface PageContainerProps {
  title: ReactNode
  actions?: ReactNode
  children: ReactNode
}

export function PageContainer({ title, actions, children }: PageContainerProps) {
  return (
    <div className="flex flex-1 flex-col">
      {/* Page header */}
      <div className="border-b bg-background px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-auto p-6">
        {children}
      </div>
    </div>
  )
}
