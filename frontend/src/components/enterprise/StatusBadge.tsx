import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const displayLabel = label || status.replace(/_/g, ' ')

  const getVariantStyles = (st: string) => {
    const uppercaseStatus = st.toUpperCase()
    switch (uppercaseStatus) {
      case 'APPROVED':
      case 'RECEIVED':
      case 'ACTIVE':
      case 'PUBLISHED':
      case 'COMPLETED':
      case 'NORMAL':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200/60 fill-emerald-500'
      case 'SUBMITTED':
      case 'RESERVED':
      case 'PENDING':
      case 'IN_PROGRESS':
        return 'bg-blue-50 text-blue-700 border-blue-200/60 fill-blue-500'
      case 'PARTIALLY_APPROVED':
      case 'DISPATCHED':
      case 'WARNING':
      case 'LOW_STOCK':
        return 'bg-amber-50 text-amber-700 border-amber-200/60 fill-amber-500'
      case 'REJECTED':
      case 'CLOSED':
      case 'FAILED':
      case 'CRITICAL':
      case 'OUT_OF_STOCK':
      case 'ARCHIVED':
        return 'bg-red-50 text-red-700 border-red-200/60 fill-red-500'
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200/60 fill-slate-400'
    }
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold capitalize transition-colors',
        getVariantStyles(status),
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {displayLabel}
    </span>
  )
}
