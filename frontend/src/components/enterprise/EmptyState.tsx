import React from 'react'
import { PackageOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface EmptyStateProps {
  title?: string
  description?: string
  icon?: React.ElementType
  actionLabel?: string
  onAction?: () => void
}

export function EmptyState({
  title = 'No records found',
  description = 'There are no items matching your criteria or currently available in the system.',
  icon: Icon = PackageOpen,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-10 text-center my-2 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-sm border border-slate-100 text-blue-600 mb-3">
        <Icon className="h-7 w-7" />
      </div>
      <h3 className="text-base font-bold text-slate-900">{title}</h3>
      <p className="mt-1 text-xs text-slate-500 max-w-sm font-medium">{description}</p>
      {actionLabel && onAction && (
        <Button onClick={onAction} className="mt-4 rounded-xl bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs h-9 px-4 shadow-sm">
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
