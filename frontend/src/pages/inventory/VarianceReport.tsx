import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { downloadBlob } from '@/api/reports'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { Download, AlertCircle, CheckCircle2, FileSpreadsheet } from 'lucide-react'
import { formatDate, getErrorMessage } from '@/lib/utils'
import { toast } from 'sonner'

export function VarianceReportPage() {
  const [page, setPage] = useState(1)
  const [snapshotDate, setSnapshotDate] = useState('')
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['inventory', 'variance-report', page, snapshotDate],
    queryFn: () =>
      inventoryApi.getVarianceReport({ page, page_size: 50, snapshot_date: snapshotDate || undefined }),
  })

  const [isExporting, setIsExporting] = useState(false)
  const handleExport = async () => {
    try {
      setIsExporting(true)
      const res = await inventoryApi.exportVarianceReport({
        snapshot_date: snapshotDate || undefined,
        format: 'excel',
      })
      const exportDate = snapshotDate || new Date().toISOString().split('T')[0]
      downloadBlob(res.data as any, `Variance_Report_${exportDate}.xlsx`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setIsExporting(false)
    }
  }

  const allItems = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const items = useMemo(() => {
    return allItems.filter(
      (i: any) =>
        i.material_name.toLowerCase().includes(search.toLowerCase()) ||
        i.material_code.toLowerCase().includes(search.toLowerCase()) ||
        i.warehouse_name.toLowerCase().includes(search.toLowerCase())
    )
  }, [allItems, search])

  const totalItems = meta?.total || allItems.length
  const matchedItems = useMemo(
    () => allItems.filter((i: any) => parseFloat(i.variance) === 0).length,
    [allItems]
  )
  const varianceItems = useMemo(
    () => allItems.filter((i: any) => parseFloat(i.variance) !== 0).length,
    [allItems]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventory Variance Audit"
        subtitle="Cross-comparison of physical EOD snapshot balances vs real-time ledger entries"
        badgeText={totalItems}
      >
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={snapshotDate}
            onChange={(e) => {
              setSnapshotDate(e.target.value)
              setPage(1)
            }}
            className="w-[160px] h-9 rounded-xl border-slate-200 text-xs shadow-sm bg-white"
            title="Filter by Business Date"
          />
          <Button
            variant="outline"
            onClick={handleExport}
            disabled={allItems.length === 0 || isExporting}
            className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 h-9 text-xs font-semibold shadow-sm"
          >
            <Download className="mr-1.5 h-3.5 w-3.5 text-slate-500" /> Export Report
          </Button>
        </div>
      </PageHeader>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Audited Records"
          value={totalItems}
          subtext="Snapshot Entries Checked"
          icon={FileSpreadsheet}
        />
        <MetricCard
          title="Matched Balances"
          value={matchedItems}
          subtext="0 Discrepancy Found"
          icon={CheckCircle2}
          badge={{ text: '100% Match', variant: 'success' }}
        />
        <MetricCard
          title="Variance Discrepancies"
          value={varianceItems}
          subtext="Items Requiring Adjustment"
          icon={AlertCircle}
          badge={{ text: varianceItems > 0 ? 'Discrepancy' : 'Clean', variant: varianceItems > 0 ? 'danger' : 'default' }}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search material name, code, or facility..."
        />

        <Table
          headers={['Material Description', 'Code', 'Facility', 'Snapshot Date', 'Snapshot Qty', 'Ledger Qty', 'Variance Qty', 'Variance %', 'UoM']}
          isLoading={isLoading}
          isEmpty={items.length === 0}
          emptyMessage="No variance records found matching criteria."
          className="border-0 shadow-none rounded-none"
        >
          {items.map((b: any) => {
            const variance = parseFloat(b.variance)
            const hasVariance = variance !== 0
            return (
              <Tr key={`${b.material_public_id}-${b.warehouse_public_id}`}>
                <Td className="font-semibold text-slate-900">{b.material_name}</Td>
                <Td className="font-mono text-xs text-slate-700 font-semibold">{b.material_code}</Td>
                <Td className="text-slate-600 font-medium">{b.warehouse_name}</Td>
                <Td className="text-slate-500 text-xs">{b.snapshot_date ? formatDate(b.snapshot_date) : 'N/A'}</Td>
                <Td className="font-medium text-slate-900">
                  {parseFloat(b.snapshot_balance).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </Td>
                <Td className="font-medium text-slate-900">
                  {parseFloat(b.current_ledger_balance).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </Td>
                <Td>
                  {hasVariance ? (
                    <StatusBadge
                      status={variance > 0 ? 'WARNING' : 'CRITICAL'}
                      label={variance > 0 ? `+${variance}` : `${variance}`}
                    />
                  ) : (
                    <StatusBadge status="NORMAL" label="Matched" />
                  )}
                </Td>
                <Td className={`font-semibold text-xs ${hasVariance ? (variance < 0 ? 'text-red-600' : 'text-emerald-700') : 'text-slate-400'}`}>
                  {b.variance_percentage === 'N/A' ? 'N/A' : `${b.variance_percentage}%`}
                </Td>
                <Td className="font-mono text-slate-500 text-xs">{b.uom}</Td>
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
