import { cn, STATUS_COLORS, TX_TYPE_COLORS } from '@/lib/utils'

interface BadgeProps {
  label: string
  variant?: 'status' | 'txType' | 'default' | 'rm' | 'pm'
  className?: string
}

export function Badge({ label, variant = 'default', className }: BadgeProps) {
  let colorClass = 'bg-gray-100 text-gray-700 border-gray-200'

  if (variant === 'status') {
    colorClass = STATUS_COLORS[label] ?? colorClass
  } else if (variant === 'txType') {
    colorClass = TX_TYPE_COLORS[label] ?? colorClass
  } else if (variant === 'rm') {
    colorClass = 'bg-blue-50 text-blue-700 border-blue-200'
  } else if (variant === 'pm') {
    colorClass = 'bg-purple-50 text-purple-700 border-purple-200'
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        colorClass,
        className
      )}
    >
      {label}
    </span>
  )
}
