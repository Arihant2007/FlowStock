import React from 'react'

interface PageHeaderProps {
  title: string
  subtitle?: string
  description?: string
  badgeText?: string | number
  children?: React.ReactNode
}

export function PageHeader({ title, subtitle, description, badgeText, children }: PageHeaderProps) {
  const subText = subtitle || description
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">{title}</h1>
          {badgeText !== undefined && (
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 border border-blue-100">
              {badgeText}
            </span>
          )}
        </div>
        {subText && <p className="mt-1 text-sm font-medium text-slate-500">{subText}</p>}
      </div>

      {children && <div className="flex items-center gap-3 shrink-0">{children}</div>}
    </div>
  )
}
