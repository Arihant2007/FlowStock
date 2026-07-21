import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { Package, Database, Lock } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsTransactionsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['reports', 'ledger', page],
    queryFn: () => reportsApi.getLedger({ page, page_size: 20 }),
  })

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const res = await reportsApi.exportLedger({ format })
      const filename = `Current_Inventory_Ledger_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`
      downloadBlob(res.data, filename)
    } catch (err) {
      console.error('Export failed', err)
    }
  }

  const allBalances = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const balances = useMemo(() => {
    return allBalances.filter(
      (b: any) =>
        b.material_name.toLowerCase().includes(search.toLowerCase()) ||
        b.material_code.toLowerCase().includes(search.toLowerCase()) ||
        b.warehouse_name.toLowerCase().includes(search.toLowerCase())
    )
  }, [allBalances, search])

  const totalAvailable = useMemo(
    () => allBalances.reduce((sum: number, b: any) => sum + parseFloat(b.available_balance || '0'), 0),
    [allBalances]
  )
  const totalReserved = useMemo(
    () => allBalances.reduce((sum: number, b: any) => sum + parseFloat(b.reserved_balance || '0'), 0),
    [allBalances]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventory Ledger Report"
        subtitle="Complete master balance snapshot across all ODS and RMPM warehouse locations"
        badgeText={meta?.total ?? allBalances.length}
      >
        <ExportButton onExport={handleExport} disabled={allBalances.length === 0} />
      </PageHeader>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Ledger Records"
          value={meta?.total || allBalances.length}
          subtext="Active Stock Entries"
          icon={Database}
        />
        <MetricCard
          title="Net Available Quantity"
          value={totalAvailable.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          subtext="Unreserved Stock On Hand"
          icon={Package}
          badge={{ text: 'Available', variant: 'success' }}
        />
        <MetricCard
          title="Total Reserved Quantity"
          value={totalReserved.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          subtext="Allocated Stock Units"
          icon={Lock}
          badge={{ text: 'Reserved', variant: 'info' }}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search material name, code, or warehouse..."
        />

        <Table
          headers={['Warehouse Facility', 'Material Code', 'Material Description', 'UoM', 'Available Balance', 'Reserved Qty', 'Health']}
          isLoading={isLoading}
          isEmpty={balances.length === 0}
          emptyMessage="No ledger data matches criteria."
          className="border-0 shadow-none rounded-none"
        >
          {balances.map((row: any, i: number) => {
            const isLowStock = parseFloat(row.available_balance) < 10
            return (
              <Tr key={i}>
                <Td className="font-semibold text-slate-900">{row.warehouse_name}</Td>
                <Td className="font-mono text-xs text-slate-700 font-semibold">{row.material_code}</Td>
                <Td className="font-medium text-slate-900">{row.material_name}</Td>
                <Td className="font-mono text-slate-500 text-xs">{row.uom}</Td>
                <Td className={`font-semibold ${isLowStock ? 'text-red-600' : 'text-slate-900'}`}>
                  {parseFloat(row.available_balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Td>
                <Td className={`font-medium ${parseFloat(row.reserved_balance) > 0 ? 'text-blue-700' : 'text-slate-400'}`}>
                  {parseFloat(row.reserved_balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Td>
                <Td>
                  <StatusBadge
                    status={isLowStock ? 'LOW_STOCK' : 'NORMAL'}
                    label={isLowStock ? 'Low Stock' : 'Healthy'}
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
