import React from 'react'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'
import { EmptyState } from '@/components/enterprise/EmptyState'

interface TableProps {
  headers: (string | React.ReactNode)[]
  children: React.ReactNode
  isLoading?: boolean
  isEmpty?: boolean
  emptyMessage?: string
  className?: string
}

export function Table({
  headers,
  children,
  isLoading,
  isEmpty,
  emptyMessage = 'No records available.',
  className,
}: TableProps) {
  return (
    <div className={cn('relative w-full overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.02)]', className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] sticky top-0 z-10">
            <tr>
              {headers.map((h, i) => (
                <th
                  key={typeof h === 'string' ? h : i}
                  className="h-12 px-6 align-middle text-[12px] font-bold tracking-wider text-slate-500 uppercase whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading ? (
              <tr>
                <td colSpan={headers.length} className="py-16 text-center">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Loader2 className="h-6 w-6 animate-spin text-[#2563EB]" />
                    <span className="text-xs font-semibold text-slate-400">Loading data...</span>
                  </div>
                </td>
              </tr>
            ) : isEmpty ? (
              <tr>
                <td colSpan={headers.length} className="p-4">
                  <EmptyState title="No results found" description={emptyMessage} />
                </td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function Tr({
  children,
  className,
  onClick,
}: {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <tr
      className={cn(
        'transition-colors duration-150 even:bg-[#FDFDFE] hover:bg-[#F8FAFC]',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  )
}

export function Td({
  children,
  className,
  title,
}: {
  children: React.ReactNode
  className?: string
  title?: string
}) {
  return (
    <td className={cn('px-6 py-4 align-middle text-slate-800 font-medium text-xs whitespace-nowrap', className)} title={title}>
      {children}
    </td>
  )
}
