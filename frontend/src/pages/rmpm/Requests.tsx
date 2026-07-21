import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { requestsApi } from '@/api/requests'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { formatDate, formatDateTime } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { ActionMenu } from '@/components/enterprise/ActionMenu'
import { ClipboardList, Clock, CheckCircle2, ArrowRight } from 'lucide-react'

export function RMPMRequestsPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const { data, isLoading } = useQuery({
    queryKey: ['requests', 'rmpm', page],
    queryFn: () => requestsApi.listRequests(page, 20),
  })

  const requests = useMemo(() => data?.data ?? [], [data])
  const meta = data?.meta

  const filteredRequests = useMemo(() => {
    return requests.filter((r) => {
      const matchesSearch =
        r.public_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (r.notes || '').toLowerCase().includes(searchTerm.toLowerCase())
      const matchesStatus = statusFilter === 'ALL' || r.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [requests, searchTerm, statusFilter])

  const pendingCount = useMemo(
    () => requests.filter((r) => ['SUBMITTED', 'RESERVED'].includes(r.status)).length,
    [requests]
  )
  const completedCount = useMemo(
    () => requests.filter((r) => ['APPROVED', 'COMPLETED', 'DISPATCHED'].includes(r.status)).length,
    [requests]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pending RMPM Approvals"
        subtitle="Review, approve, and manage material allocation requests from ODS units"
        badgeText={meta?.total ?? requests.length}
      />

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Queue Size"
          value={meta?.total || requests.length}
          subtext="Incoming Requests"
          icon={ClipboardList}
        />
        <MetricCard
          title="Action Required"
          value={pendingCount}
          subtext="High Priority Requests"
          icon={Clock}
          badge={{ text: 'Action Req', variant: 'danger' }}
        />
        <MetricCard
          title="Approved Requests"
          value={completedCount}
          subtext="Material Dispatched"
          icon={CheckCircle2}
          badge={{ text: 'Completed', variant: 'success' }}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search request ID or notes..."
        >
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 rounded-xl border border-slate-200 bg-slate-50/50 px-3 text-xs font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Request Statuses</option>
            <option value="SUBMITTED">Submitted (Pending)</option>
            <option value="RESERVED">Reserved</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </TableToolbar>

        <Table
          headers={['Request Reference ID', 'Request Date', 'Approval Status', 'Notes / Remarks', 'Timestamp', 'Action']}
          isLoading={isLoading}
          isEmpty={filteredRequests.length === 0}
          emptyMessage="No pending approval requests found matching search."
          className="border-0 shadow-none rounded-none"
        >
          {filteredRequests.map((r) => (
            <Tr
              key={r.public_id}
              onClick={() => navigate(`/rmpm/requests/${r.public_id}`)}
              className="cursor-pointer"
            >
              <Td className="font-mono text-xs font-semibold text-blue-700">{r.public_id}</Td>
              <Td className="font-semibold text-slate-900">{formatDate(r.request_date)}</Td>
              <Td>
                <StatusBadge status={r.status} />
              </Td>
              <Td className="text-slate-500 text-xs max-w-xs truncate">{r.notes || '—'}</Td>
              <Td className="text-slate-500 text-xs">{formatDateTime(r.created_at)}</Td>
              <Td>
                <ActionMenu
                  items={[
                    {
                      label: 'Review & Approve',
                      icon: ArrowRight,
                      onClick: () => navigate(`/rmpm/requests/${r.public_id}`),
                    },
                  ]}
                />
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
