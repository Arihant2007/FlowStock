import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { FileDown, CheckCircle2, List } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsRequestsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['reports', 'requests', page],
    queryFn: () => reportsApi.getRequests({ page, page_size: 20 }),
  })

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const res = await reportsApi.exportRequests({ format })
      const filename = `Material_Requests_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`
      downloadBlob(res.data, filename)
    } catch (err) {
      console.error('Export failed', err)
    }
  }

  const allRequests = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const requests = useMemo(() => {
    return allRequests.filter((req: any) =>
      `REQ-${req.id}`.toLowerCase().includes(search.toLowerCase())
    )
  }, [allRequests, search])

  const completedCount = useMemo(
    () =>
      allRequests.filter((req: any) => req.status === 'CLOSED' || req.status === 'RECEIVED').length,
    [allRequests]
  )
  const totalSkus = useMemo(
    () => allRequests.reduce((sum: number, req: any) => sum + (req.skus?.length || 0), 0),
    [allRequests]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Material Requests Report"
        subtitle="Audit logs of ODS material requests, fulfillment stages, and planned SKU counts"
        badgeText={meta?.total ?? allRequests.length}
      >
        <ExportButton onExport={handleExport} disabled={allRequests.length === 0} />
      </PageHeader>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Logged Requests"
          value={meta?.total || allRequests.length}
          subtext="ODS Supply Stream"
          icon={List}
        />
        <MetricCard
          title="Completed & Fulfilled"
          value={completedCount}
          subtext="Closed / Received Requests"
          icon={CheckCircle2}
          badge={{ text: 'Completed', variant: 'success' }}
        />
        <MetricCard
          title="Total Production SKUs"
          value={totalSkus}
          subtext="SKU Batches Included"
          icon={FileDown}
          badge={{ text: 'Batch Count', variant: 'info' }}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search by request ID..."
        />

        <Table
          headers={['Request Reference', 'Request Date', 'Fulfillment Status', 'Included SKUs', 'Operator ID']}
          isLoading={isLoading}
          isEmpty={requests.length === 0}
          emptyMessage="No material request reports match query."
          className="border-0 shadow-none rounded-none"
        >
          {requests.map((req: any) => (
            <Tr key={req.id}>
              <Td className="font-mono text-xs font-semibold text-blue-700">REQ-{req.id}</Td>
              <Td className="text-slate-600 font-semibold text-xs">{req.request_date}</Td>
              <Td>
                <StatusBadge status={req.status} />
              </Td>
              <Td className="text-slate-900 font-medium text-xs">{req.skus?.length || 0} SKUs</Td>
              <Td className="text-slate-500 text-xs">Operator #{req.created_by}</Td>
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
