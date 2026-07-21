import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { Package, AlertTriangle, ArrowUpRight } from 'lucide-react'

export function InventoryBalancesPage() {
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const { data, isLoading } = useQuery({
    queryKey: ['inventory', 'balances', page],
    queryFn: () => inventoryApi.getBalances(page, 50),
  })

  const balances = useMemo(() => data?.data ?? [], [data])
  const meta = data?.meta

  const filteredBalances = useMemo(() => {
    return balances.filter((b) => {
      const matchesSearch =
        b.material_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        b.material_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
        b.warehouse_name.toLowerCase().includes(searchTerm.toLowerCase())
      const available = parseFloat(b.available_balance)
      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'LOW' && available < 10) ||
        (statusFilter === 'HEALTHY' && available >= 10)
      return matchesSearch && matchesStatus
    })
  }, [balances, searchTerm, statusFilter])

  const lowStockCount = useMemo(
    () => balances.filter((b) => parseFloat(b.available_balance) < 10).length,
    [balances]
  )
  const totalReserved = useMemo(
    () => balances.reduce((sum, b) => sum + parseFloat(b.reserved_balance), 0),
    [balances]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock Ledger & Balances"
        subtitle="Real-time material availability, reserved quantities, and warehouse locations"
        badgeText={meta?.total ?? balances.length}
      />

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Active Materials"
          value={balances.length}
          subtext="Materials in Stock"
          icon={Package}
        />
        <MetricCard
          title="Low Stock Alerts"
          value={lowStockCount}
          subtext="Items Below Minimum Threshold"
          icon={AlertTriangle}
          badge={{ text: lowStockCount > 0 ? 'Requires Action' : 'Optimal', variant: lowStockCount > 0 ? 'warning' : 'success' }}
        />
        <MetricCard
          title="Total Reserved Qty"
          value={totalReserved.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          subtext="Allocated to Pending ODS Requests"
          icon={ArrowUpRight}
          badge={{ text: 'Allocated', variant: 'info' }}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search material name, code, or warehouse..."
        >
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-xl border border-slate-200 bg-slate-50/50 px-3 text-xs font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Stock Levels</option>
            <option value="HEALTHY font-medium">Healthy Stock (≥ 10)</option>
            <option value="LOW">Low Stock (&lt; 10)</option>
          </select>
        </TableToolbar>

        <Table
          headers={['Material Description', 'Code', 'Warehouse Facility', 'Available Balance', 'Reserved Qty', 'UoM', 'Stock Health']}
          isLoading={isLoading}
          isEmpty={filteredBalances.length === 0}
          emptyMessage="No stock balances match your search query."
          className="border-0 shadow-none rounded-none"
        >
          {filteredBalances.map((b) => {
            const available = parseFloat(b.available_balance)
            const isLowStock = available < 10
            const hasReserved = parseFloat(b.reserved_balance) > 0

            return (
              <Tr key={`${b.material_public_id}-${b.warehouse_public_id}`}>
                <Td className="font-semibold text-slate-900">{b.material_name}</Td>
                <Td className="font-mono text-xs text-slate-700 font-semibold">{b.material_code}</Td>
                <Td className="text-slate-600 font-medium">{b.warehouse_name}</Td>
                <Td className={`font-semibold ${isLowStock ? 'text-red-600 font-bold' : 'text-slate-900'}`}>
                  {available.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Td>
                <Td className={`font-medium ${hasReserved ? 'text-blue-700' : 'text-slate-400'}`}>
                  {parseFloat(b.reserved_balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </Td>
                <Td className="font-mono text-slate-500 text-xs">{b.uom}</Td>
                <Td>
                  <StatusBadge
                    status={isLowStock ? 'LOW_STOCK' : 'NORMAL'}
                    label={isLowStock ? 'Low Stock Alert' : 'Healthy Stock'}
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
