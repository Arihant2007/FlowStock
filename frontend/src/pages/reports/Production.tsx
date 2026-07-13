import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { Settings } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsProductionPage() {
  const [page, setPage] = useState(1)

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

  const productionData = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Settings className="h-6 w-6" /> Daily Production Report
          </h1>
          <p className="text-muted-foreground text-sm">Review daily production metrics, material consumption, and yields.</p>
        </div>
        <ExportButton onExport={handleExport} disabled={productionData.length === 0} />
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Date', 'SKU', 'Planned Qty', 'Material', 'Gross Req', 'Consumed']}
            isLoading={isLoading}
            isEmpty={productionData.length === 0}
            emptyMessage="No production records found."
          >
            {productionData.map((row: any, i: number) => (
              <Tr key={i}>
                <Td className="font-medium">{row.date}</Td>
                <Td className="font-mono text-xs">{row.sku}</Td>
                <Td>{row.planned_fg_qty}</Td>
                <Td className="font-mono text-xs">{row.material}</Td>
                <Td>{row.gross_requirement}</Td>
                <Td className="font-semibold text-green-700">{row.consumed}</Td>
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
