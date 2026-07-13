import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, downloadBlob } from '@/api/reports'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { FileText } from 'lucide-react'
import { ExportButton } from '@/components/ui/export-button'

export function ReportsTransactionsPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['reports', 'ledger', page],
    queryFn: () => reportsApi.getLedger({ page, page_size: 20 }),
  })

  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const res = await reportsApi.exportLedger({ format })
      const filename = `Current_Inventory_Ledger_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : 'csv'}`
      downloadBlob(res.data, filename)
    } catch (err) {
      console.error('Export failed', err)
    }
  }

  const balances = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6" /> Current Inventory Ledger
          </h1>
          <p className="text-muted-foreground text-sm">View and export real-time stock balances across all warehouses.</p>
        </div>
        <ExportButton onExport={handleExport} disabled={balances.length === 0} />
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Warehouse', 'Material Code', 'Material Name', 'UoM', 'Available', 'Reserved']}
            isLoading={isLoading}
            isEmpty={balances.length === 0}
            emptyMessage="No ledger data found."
          >
            {balances.map((row: any, i: number) => (
              <Tr key={i}>
                <Td className="font-medium">{row.warehouse_name}</Td>
                <Td className="font-mono text-xs">{row.material_code}</Td>
                <Td>{row.material_name}</Td>
                <Td className="text-muted-foreground">{row.uom}</Td>
                <Td className="font-semibold text-green-700">{row.available_balance}</Td>
                <Td className="text-orange-600">{row.reserved_balance}</Td>
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
