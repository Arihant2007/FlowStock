import React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  title: string
  value: string | number
  subtext?: string
  lastUpdated?: string
  icon?: React.ElementType
  iconColor?: string
  trend?: {
    value: string | number
    label?: string
    isPositive?: boolean
  }
  badge?: {
    text: string
    variant?: 'default' | 'warning' | 'danger' | 'success' | 'info'
  }
  className?: string
  onClick?: () => void
}

export function MetricCard({
  title,
  value,
  subtext,
  lastUpdated = 'Updated today',
  icon: Icon,
  iconColor = 'bg-blue-50 text-[#2563EB]',
  trend,
  badge,
  className,
  onClick,
}: MetricCardProps) {
  return (
    <motion.div
      whileHover={onClick ? { y: -2, transition: { duration: 0.2 } } : undefined}
      onClick={onClick}
      className={cn(
        'relative overflow-hidden rounded-2xl bg-white p-5 shadow-[0_2px_12px_rgba(0,0,0,0.03)] border border-[#E2E8F0] hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)] hover:border-slate-300 transition-all duration-200 flex flex-col justify-between',
        onClick && 'cursor-pointer',
        className
      )}
    >
      <div>
        <div className="flex items-start justify-between">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{title}</p>
          {Icon && (
            <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl shadow-xs', iconColor)}>
              <Icon className="h-5.5 w-5.5" />
            </div>
          )}
        </div>
        <h3 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
          {value}
        </h3>
      </div>

      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
        <div className="flex flex-col">
          {subtext && <span className="font-semibold text-slate-700">{subtext}</span>}
          <span className="text-[11px] font-medium text-slate-400 mt-0.5">{lastUpdated}</span>
        </div>
        {badge && (
          <span
            className={cn(
              'inline-flex items-center rounded-md px-2 py-0.5 font-bold text-[11px]',
              badge.variant === 'warning' && 'bg-amber-50 text-amber-800 border border-amber-200/60',
              badge.variant === 'danger' && 'bg-red-50 text-red-800 border border-red-200/60',
              badge.variant === 'success' && 'bg-emerald-50 text-emerald-800 border border-emerald-200/60',
              badge.variant === 'info' && 'bg-blue-50 text-blue-800 border border-blue-200/60',
              (!badge.variant || badge.variant === 'default') && 'bg-slate-100 text-slate-700'
            )}
          >
            {badge.text}
          </span>
        )}
        {trend && (
          <span
            className={cn(
              'font-semibold text-xs',
              trend.isPositive ? 'text-emerald-600' : 'text-slate-500'
            )}
          >
            {trend.value} {trend.label && <span className="font-normal text-slate-400">{trend.label}</span>}
          </span>
        )}
      </div>
    </motion.div>
  )
}
