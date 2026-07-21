import React from 'react'
import { MoreHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface ActionItem {
  label: string
  icon?: React.ElementType
  onClick: () => void
  variant?: 'default' | 'destructive'
}

interface ActionMenuProps {
  items: ActionItem[]
}

export function ActionMenu({ items }: ActionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44 rounded-xl shadow-lg border-slate-100 p-1">
        {items.map((item, index) => (
          <DropdownMenuItem
            key={index}
            onClick={item.onClick}
            className={`cursor-pointer rounded-lg text-xs px-3 py-2 ${
              item.variant === 'destructive'
                ? 'text-red-600 focus:bg-red-50 focus:text-red-700'
                : 'text-slate-700 focus:bg-slate-100'
            }`}
          >
            {item.icon && <item.icon className="mr-2 h-3.5 w-3.5" />}
            {item.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
