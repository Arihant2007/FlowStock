import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { FileDown } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsRequestsPage() {
  const [page, setPage] = useState(1)

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

  const requests = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileDown className="h-6 w-6" /> Material Requests Report
          </h1>
          <p className="text-muted-foreground text-sm">Review details of daily material requests including planned vs actual dispatch.</p>
        </div>
        <ExportButton onExport={handleExport} disabled={requests.length === 0} />
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Request ID', 'Date', 'Status', 'SKUs', 'Requested By']}
            isLoading={isLoading}
            isEmpty={requests.length === 0}
            emptyMessage="No material requests found."
          >
            {requests.map((req: any) => (
              <Tr key={req.id}>
                <Td className="font-medium text-xs font-mono">REQ-{req.id}</Td>
                <Td>{req.request_date}</Td>
                <Td>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    req.status === 'APPROVED' ? 'bg-blue-100 text-blue-800' :
                    req.status === 'DISPATCHED' ? 'bg-indigo-100 text-indigo-800' :
                    req.status === 'RECEIVED' ? 'bg-teal-100 text-teal-800' :
                    req.status === 'CLOSED' ? 'bg-green-100 text-green-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {req.status}
                  </span>
                </Td>
                <Td>{req.skus?.length || 0} SKUs</Td>
                <Td className="text-muted-foreground">User {req.created_by}</Td>
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
