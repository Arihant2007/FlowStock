import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { masterApi } from '@/api/master'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Pagination } from '@/components/ui/pagination'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { getErrorMessage, formatDate } from '@/lib/utils'
import { Package, Trash2, Upload } from 'lucide-react'

export function MaterialsPage() {
  const { hasPermission } = useAuth()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState<string | undefined>()
  const [deleteName, setDeleteName] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['master', 'materials', page],
    queryFn: () => masterApi.listMaterials(page),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => masterApi.deleteMaterial(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'materials'] })
      toast.success('Material deleted.')
      setDeleteTarget(undefined)
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const materials = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Package className="h-6 w-6" /> Materials
          </h1>
          <p className="text-muted-foreground text-sm">Raw materials (RM) and packaging materials (PM)</p>
        </div>
        {hasPermission('master:write') && (
          <Link to="/master/material-upload">
            <Button className="flex items-center gap-2">
              <Upload className="h-4 w-4" /> Upload Excel
            </Button>
          </Link>
        )}
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Code', 'Name', 'Type', 'Category', 'UoM', 'Created', ...(hasPermission('master:write') ? ['Actions'] : [])]}
            isLoading={isLoading}
            isEmpty={materials.length === 0}
            emptyMessage="No materials found."
          >
            {materials.map((m) => (
              <Tr key={m.public_id}>
                <Td className="font-mono font-medium text-sm">{m.code}</Td>
                <Td>{m.name}</Td>
                <Td>
                  {m.material_type && (
                    <Badge
                      label={m.material_type.name}
                      variant={m.material_type.name === 'RM' ? 'rm' : 'pm'}
                    />
                  )}
                </Td>
                <Td className="text-muted-foreground">{m.category?.name ?? '—'}</Td>
                <Td>{m.uom}</Td>
                <Td className="text-muted-foreground">{formatDate(m.created_at)}</Td>
                {hasPermission('master:write') && (
                  <Td>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => { setDeleteTarget(m.public_id); setDeleteName(m.name) }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </Td>
                )}
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

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => !v && setDeleteTarget(undefined)}
        title="Delete Material"
        description={`Are you sure you want to delete "${deleteName}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  )
}
