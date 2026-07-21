import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { requestsApi } from '@/api/requests'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { formatDate, formatDateTime } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { ActionMenu } from '@/components/enterprise/ActionMenu'
import { BookOpen, Clock, CheckCircle2, Plus, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ODSRequestsPage() {
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')

  const { data, isLoading } = useQuery({
    queryKey: ['requests', 'ods', page],
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
        title="ODS Material Requests"
        subtitle="Track, monitor, and submit material transfer requests for production lines"
        badgeText={meta?.total ?? requests.length}
      >
        <Link to="/ods/new-request">
          <Button className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-9 text-xs font-semibold shadow-sm">
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Create New Request
          </Button>
        </Link>
      </PageHeader>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Submitted Requests"
          value={meta?.total || requests.length}
          subtext="ODS Supply Stream"
          icon={BookOpen}
        />
        <MetricCard
          title="Pending Approvals"
          value={pendingCount}
          subtext="Awaiting RMPM Review"
          icon={Clock}
          badge={{ text: 'Pending', variant: 'warning' }}
        />
        <MetricCard
          title="Fulfilling / Approved"
          value={completedCount}
          subtext="Dispatched to Production"
          icon={CheckCircle2}
          badge={{ text: 'Approved', variant: 'success' }}
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
            <option value="SUBMITTED">Submitted</option>
            <option value="RESERVED">Reserved</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </TableToolbar>

        <Table
          headers={['Request Reference ID', 'Request Date', 'Status', 'Notes', 'Created Timestamp', 'Action']}
          isLoading={isLoading}
          isEmpty={filteredRequests.length === 0}
          emptyMessage="No material requests match your filter criteria."
          className="border-0 shadow-none rounded-none"
        >
          {filteredRequests.map((r) => (
            <Tr key={r.public_id}>
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
                      label: 'View Request Log',
                      icon: Eye,
                      onClick: () => {},
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
