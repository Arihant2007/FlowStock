import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { BarChart, CheckCircle2, Factory } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsProductionPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['reports', 'production', page],
    queryFn: () => reportsApi.getProduction({ page, page_size: 20 }),
  })

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const res = await reportsApi.exportProduction({ format })
      const filename = `Daily_Production_Report_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`
      downloadBlob(res.data, filename)
    } catch (err) {
      console.error('Export failed', err)
    }
  }

  const allProductionData = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const productionData = useMemo(() => {
    return allProductionData.filter(
      (r: any) =>
        (r.sku || '').toLowerCase().includes(search.toLowerCase()) ||
        (r.material || '').toLowerCase().includes(search.toLowerCase())
    )
  }, [allProductionData, search])

  const uniqueSkus = useMemo(
    () => new Set(allProductionData.map((r: any) => r.sku)).size,
    [allProductionData]
  )
  const totalConsumed = useMemo(
    () =>
      allProductionData.reduce(
        (sum: number, r: any) => sum + parseFloat(r.consumed || '0'),
        0
      ),
    [allProductionData]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Daily Production & Yield Report"
        subtitle="Review production run metrics, planned FG yields, and material consumption"
        badgeText={meta?.total ?? allProductionData.length}
      >
        <ExportButton onExport={handleExport} disabled={allProductionData.length === 0} />
      </PageHeader>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Production Runs"
          value={meta?.total || allProductionData.length}
          subtext="Logged Shift Runs"
          icon={Factory}
        />
        <MetricCard
          title="Active Manufactured SKUs"
          value={uniqueSkus}
          subtext="Unique Products"
          icon={BarChart}
          badge={{ text: 'Production', variant: 'info' }}
        />
        <MetricCard
          title="Materials Consumed"
          value={totalConsumed.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          subtext="Net Kilograms / Units"
          icon={CheckCircle2}
          badge={{ text: 'Fulfilled', variant: 'success' }}
        />
      </div>

      {/* Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search SKU code or material..."
        />

        <Table
          headers={['Production Date', 'Manufactured SKU', 'Planned FG Qty', 'Material Requirement', 'Gross Required', 'Actual Consumed Qty']}
          isLoading={isLoading}
          isEmpty={productionData.length === 0}
          emptyMessage="No production records match criteria."
          className="border-0 shadow-none rounded-none"
        >
          {productionData.map((row: any, i: number) => (
            <Tr key={i}>
              <Td className="text-slate-600 font-medium text-xs">{row.date}</Td>
              <Td className="font-mono text-xs font-semibold text-blue-700">{row.sku}</Td>
              <Td className="font-semibold text-slate-900">{row.planned_fg_qty}</Td>
              <Td className="font-mono text-xs text-slate-600 font-medium">{row.material}</Td>
              <Td className="text-slate-700 text-xs">
                {parseFloat(row.gross_requirement).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Td>
              <Td className="font-bold text-emerald-700 text-xs">
                {parseFloat(row.consumed).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Td>
            </Tr>
          ))}
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
