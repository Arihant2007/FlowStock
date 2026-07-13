import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { requestsApi } from '@/api/requests'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Pagination } from '@/components/ui/pagination'
import { formatDate, formatDateTime } from '@/lib/utils'
import { BookOpen } from 'lucide-react'

export function ODSRequestsPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['requests', 'ods', page],
    queryFn: () => requestsApi.listRequests(page, 20),
  })

  const requests = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen className="h-6 w-6" /> My Requests
        </h1>
        <p className="text-muted-foreground text-sm">View the status of your material requests.</p>
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Request ID', 'Date', 'Status', 'Notes', 'Created At']}
            isLoading={isLoading}
            isEmpty={requests.length === 0}
            emptyMessage="No requests found."
          >
            {requests.map((r) => (
              <Tr key={r.public_id}>
                <Td className="font-mono text-xs">{r.public_id}</Td>
                <Td className="font-medium">{formatDate(r.request_date)}</Td>
                <Td><Badge label={r.status} variant="status" /></Td>
                <Td className="text-muted-foreground max-w-xs truncate">{r.notes || '—'}</Td>
                <Td className="text-muted-foreground">{formatDateTime(r.created_at)}</Td>
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
