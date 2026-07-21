import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { formatDateTime, formatQty } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { BarChart3, ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsInventoryPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

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

  const allTransactions = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const transactions = useMemo(() => {
    return allTransactions.filter(
      (tx: any) =>
        `TXN-${tx.id}`.toLowerCase().includes(search.toLowerCase()) ||
        (tx.notes || '').toLowerCase().includes(search.toLowerCase())
    )
  }, [allTransactions, search])

  const surplusCount = useMemo(
    () => allTransactions.filter((tx: any) => Number(tx.quantity) > 0).length,
    [allTransactions]
  )
  const shortageCount = useMemo(
    () => allTransactions.filter((tx: any) => Number(tx.quantity) < 0).length,
    [allTransactions]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Material Variance Report"
        subtitle="Audit logs of adjustment transactions created during inventory reconciliation"
        badgeText={meta?.total ?? allTransactions.length}
      >
        <ExportButton onExport={handleExport} disabled={allTransactions.length === 0} />
      </PageHeader>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Audit Log Entries"
          value={meta?.total || allTransactions.length}
          subtext="Adjustment Records"
          icon={BarChart3}
        />
        <MetricCard
          title="Surplus Adjustments"
          value={surplusCount}
          subtext="Positive Quantity Variance"
          icon={ArrowUpRight}
          badge={{ text: 'Surplus', variant: 'success' }}
        />
        <MetricCard
          title="Shortage Adjustments"
          value={shortageCount}
          subtext="Negative Quantity Variance"
          icon={ArrowDownRight}
          badge={{ text: 'Shortage', variant: 'danger' }}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search by transaction ID or adjustment notes..."
        />

        <Table
          headers={['Timestamp', 'Transaction Reference', 'Adjustment Remarks / Reason', 'Variance Quantity']}
          isLoading={isLoading}
          isEmpty={transactions.length === 0}
          emptyMessage="No material variance transactions found."
          className="border-0 shadow-none rounded-none"
        >
          {transactions.map((tx: any) => {
            const qty = Number(tx.quantity)
            const isSurplus = qty > 0

            return (
              <Tr key={tx.id}>
                <Td className="text-slate-500 text-xs font-medium">{formatDateTime(tx.created_at)}</Td>
                <Td className="font-mono text-xs font-semibold text-slate-900">TXN-{tx.id}</Td>
                <Td className="text-slate-600 text-xs max-w-md truncate font-medium">
                  {tx.notes || 'System Reconciliation Adjustment'}
                </Td>
                <Td>
                  <StatusBadge
                    status={isSurplus ? 'NORMAL' : 'CRITICAL'}
                    label={`${isSurplus ? '+' : ''}${formatQty(tx.quantity)}`}
                  />
                </Td>
              </Tr>
            )
          })}
        </Table>

        {meta && (
          <div className="border-t border-slate-100 p-3 bg-slate-50/40">
            <Pagination
              page={meta.page}
              totalPages={meta.total_pages}
              total={meta.total}
              pageSize={meta.page_size}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  )
}
