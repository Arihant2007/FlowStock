import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { downloadBlob } from '@/api/reports'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Scale, Download, Filter } from 'lucide-react'
import { formatDate } from '@/lib/utils'
import { toast } from 'sonner'
import { getErrorMessage } from '@/lib/utils'

export function VarianceReportPage() {
  const [page, setPage] = useState(1)
  const [snapshotDate, setSnapshotDate] = useState('')
  
  const { data, isLoading } = useQuery({
    queryKey: ['inventory', 'variance-report', page, snapshotDate],
    queryFn: () => inventoryApi.getVarianceReport({ page, page_size: 50, snapshot_date: snapshotDate || undefined }),
  })

  const [isExporting, setIsExporting] = useState(false)
  const handleExport = async () => {
    try {
      setIsExporting(true)
      const res = await inventoryApi.exportVarianceReport({
        snapshot_date: snapshotDate || undefined,
        format: 'excel'
      })
      const exportDate = snapshotDate || formatDate(new Date().toISOString(), 'yyyy-MM-dd')
      downloadBlob(res.data as any, `Variance_Report_${exportDate}.xlsx`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setIsExporting(false)
    }
  }

  const items = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Scale className="h-6 w-6" /> Variance Report
          </h1>
          <p className="text-muted-foreground text-sm">Compare snapshot balances vs current ledger</p>
        </div>
        
        <div className="flex items-center gap-2">
          <Input 
            type="date"
            value={snapshotDate}
            onChange={(e) => { setSnapshotDate(e.target.value); setPage(1); }}
            className="w-[160px]"
            title="Business Date"
          />
          <Button variant="outline" onClick={handleExport} isLoading={isExporting} disabled={items.length === 0}>
            <Download className="h-4 w-4 mr-2" />
            Export Excel
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4 pb-0 overflow-auto">
          <Table
            headers={['Material', 'Code', 'Warehouse', 'Business Date', 'Snapshot Bal', 'Ledger Bal', 'Variance', 'Variance %', 'UoM']}
            isLoading={isLoading}
            isEmpty={items.length === 0}
            emptyMessage="No variance data found."
          >
            {items.map((b: any) => {
              const variance = parseFloat(b.variance)
              const hasVariance = variance !== 0
              return (
                <Tr key={`${b.material_public_id}-${b.warehouse_public_id}`}>
                  <Td className="font-medium">{b.material_name}</Td>
                  <Td className="font-mono text-sm">{b.material_code}</Td>
                  <Td>{b.warehouse_name}</Td>
                  <Td>{b.snapshot_date ? formatDate(b.snapshot_date) : 'N/A'}</Td>
                  <Td>{b.snapshot_balance}</Td>
                  <Td>{b.current_ledger_balance}</Td>
                  <Td className={hasVariance ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                    {hasVariance ? (variance > 0 ? `+${variance}` : variance) : 'Matched'}
                  </Td>
                  <Td className={hasVariance ? 'text-red-600 font-medium' : 'text-green-600'}>
                    {b.variance_percentage === 'N/A' ? 'N/A' : `${b.variance_percentage}%`}
                  </Td>
                  <Td>{b.uom}</Td>
                </Tr>
              )
            })}
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
