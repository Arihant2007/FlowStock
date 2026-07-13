import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { inventoryApi } from '@/api/inventory'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { Scale } from 'lucide-react'

export function InventoryBalancesPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['inventory', 'balances', page],
    queryFn: () => inventoryApi.getBalances(page, 50),
  })

  const balances = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Scale className="h-6 w-6" /> Inventory Balances
        </h1>
        <p className="text-muted-foreground text-sm">Real-time material availability across warehouses</p>
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Material', 'Code', 'Warehouse', 'Available', 'Reserved', 'UoM']}
            isLoading={isLoading}
            isEmpty={balances.length === 0}
            emptyMessage="No balances found."
          >
            {balances.map((b) => (
              <Tr key={`${b.material_public_id}-${b.warehouse_public_id}`}>
                <Td className="font-medium">{b.material_name}</Td>
                <Td className="font-mono text-sm">{b.material_code}</Td>
                <Td>{b.warehouse_name}</Td>
                <Td className={parseFloat(b.available_balance) < 10 ? 'text-red-600 font-semibold' : ''}>
                  {b.available_balance}
                </Td>
                <Td className="text-muted-foreground">{b.reserved_balance}</Td>
                <Td>{b.uom}</Td>
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
