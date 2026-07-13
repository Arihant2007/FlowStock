import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Pagination } from '@/components/ui/pagination'
import { formatDateTime } from '@/lib/utils'
import { History } from 'lucide-react'

export function TransactionHistoryPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['inventory', 'transactions', page],
    queryFn: () => inventoryApi.getTransactions({ page, page_size: 50 }),
  })

  const transactions = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <History className="h-6 w-6" /> Transaction History
        </h1>
        <p className="text-muted-foreground text-sm">Ledger of all inventory movements</p>
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Date', 'Type', 'Quantity', 'Reference', 'Notes']}
            isLoading={isLoading}
            isEmpty={transactions.length === 0}
            emptyMessage="No transactions found."
          >
            {transactions.map((tx) => (
              <Tr key={tx.id}>
                <Td className="whitespace-nowrap">{formatDateTime(tx.created_at)}</Td>
                <Td><Badge label={tx.transaction_type} variant="txType" /></Td>
                <Td className="font-mono text-sm">{tx.quantity}</Td>
                <Td>
                  {tx.reference_type ? (
                    <span className="text-xs border px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground">
                      {tx.reference_type} #{tx.reference_id}
                    </span>
                  ) : '—'}
                </Td>
                <Td className="text-muted-foreground text-sm max-w-sm truncate">{tx.notes || '—'}</Td>
              </Tr>
            ))}
          </Table>
        </CardContent>
        {meta && (
          <Pagination
            page={meta.page}
            totalPages={meta.total_pages}
            total={meta.total}
            pageSize={meta.page_size}
            onPageChange={setPage}
          />
        )}
      </Card>
    </div>
  )
}
