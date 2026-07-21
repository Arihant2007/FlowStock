import React from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'

interface TableToolbarProps {
  searchQuery?: string
  onSearchChange?: (query: string) => void
  searchPlaceholder?: string
  children?: React.ReactNode
}

export function TableToolbar({
  searchQuery,
  onSearchChange,
  searchPlaceholder = 'Search by name, ID, or code...',
  children,
}: TableToolbarProps) {
  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-4 bg-white border-b border-slate-100 rounded-t-2xl">
      {onSearchChange !== undefined && (
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            type="text"
            value={searchQuery || ''}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="pl-10 h-10 bg-slate-50/50 border-slate-200 text-slate-900 placeholder:text-slate-400 rounded-xl focus-visible:ring-blue-500 focus-visible:bg-white text-sm transition-all"
          />
        </div>
      )}

      <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">{children}</div>
    </div>
  )
}
