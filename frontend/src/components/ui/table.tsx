import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

interface TableProps {
  headers: string[]
  children: React.ReactNode
  isLoading?: boolean
  isEmpty?: boolean
  emptyMessage?: string
  className?: string
}

export function Table({ headers, children, isLoading, isEmpty, emptyMessage = 'No data found.', className }: TableProps) {
  return (
    <div className={cn('relative w-full overflow-auto rounded-md border', className)}>
      <table className="w-full caption-bottom text-sm">
        <thead className="[&_tr]:border-b bg-muted/40">
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                className="h-10 px-4 text-left align-middle font-medium text-muted-foreground whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_tr:last-child]:border-0">
          {isLoading ? (
            <tr>
              <td colSpan={headers.length} className="py-16 text-center">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
              </td>
            </tr>
          ) : isEmpty ? (
            <tr>
              <td colSpan={headers.length} className="py-16 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            children
          )}
        </tbody>
      </table>
    </div>
  )
}

export function Tr({ children, className, onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <tr
      className={cn('border-b transition-colors hover:bg-muted/40', onClick && 'cursor-pointer', className)}
      onClick={onClick}
    >
      {children}
    </tr>
  )
}

export function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn('px-4 py-3 align-middle', className)}>{children}</td>
}
