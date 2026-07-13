import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { formatDateTime, formatQty } from '@/lib/utils'
import { BarChart3 } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsInventoryPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['reports', 'variance', page],
    queryFn: () => reportsApi.getVariance({ page, page_size: 20 }),
  })

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const res = await reportsApi.exportVariance({ format })
      const filename = `Material_Variance_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`
      downloadBlob(res.data, filename)
    } catch (err) {
      console.error('Export failed', err)
    }
  }

  const transactions = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6" /> Material Variance Report
          </h1>
          <p className="text-muted-foreground text-sm">Review adjustment transactions created during inventory reconciliation.</p>
        </div>
        <ExportButton onExport={handleExport} disabled={transactions.length === 0} />
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Date', 'Transaction ID', 'Notes', 'Variance (Qty)']}
            isLoading={isLoading}
            isEmpty={transactions.length === 0}
            emptyMessage="No variance transactions found."
          >
            {transactions.map((tx: any) => {
              const qty = Number(tx.quantity)
              const isSurplus = qty > 0
              return (
                <Tr key={tx.id}>
                  <Td className="font-medium">{formatDateTime(tx.created_at)}</Td>
                  <Td className="font-mono text-xs text-muted-foreground">TXN-{tx.id}</Td>
                  <Td className="text-muted-foreground max-w-sm truncate">{tx.notes || 'System Adjustment'}</Td>
                  <Td>
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold border ${isSurplus ? 'text-green-700 bg-green-50 border-green-200' : 'text-red-700 bg-red-50 border-red-200'}`}
                    >
                      {isSurplus ? '+' : ''}{formatQty(tx.quantity)}
                    </span>
                  </Td>
                </Tr>
              )
            })}
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
