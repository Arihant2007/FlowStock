import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { masterApi } from '@/api/master'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { getErrorMessage, formatDate } from '@/lib/utils'
import { Plus, Pencil, Trash2, Layers } from 'lucide-react'
import type { SKUOut } from '@/types/api'

const skuSchema = z.object({
  code: z.string().min(1).max(100),
  name: z.string().min(1).max(255),
  description: z.string().max(2000).optional(),
})
type SKUForm = z.infer<typeof skuSchema>

function SKUDialog({ open, onOpenChange, sku }: { open: boolean; onOpenChange: (v: boolean) => void; sku?: SKUOut }) {
  const qc = useQueryClient()
  const isEdit = !!sku
  const { register, handleSubmit, formState: { errors, isSubmitting }, reset } = useForm<SKUForm>({
    resolver: zodResolver(skuSchema as any),
    defaultValues: sku ? { code: sku.code, name: sku.name, description: sku.description } : undefined,
  })

  const mutation = useMutation({
    mutationFn: async (data: SKUForm) => {
      if (isEdit && sku) return masterApi.updateSKU(sku.public_id, { name: data.name, description: data.description ?? '', version: 1 })
      return masterApi.createSKU({ ...data, description: data.description ?? '' })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'skus'] })
      toast.success(isEdit ? 'SKU updated.' : 'SKU created.')
      onOpenChange(false)
      reset()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{isEdit ? 'Edit SKU' : 'Create SKU'}</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          {!isEdit && (
            <div className="space-y-1.5">
              <Label>Code</Label>
              <Input placeholder="SKU-BISCUIT-500" {...register('code')} />
              {errors.code && <p className="text-xs text-destructive">{errors.code.message}</p>}
            </div>
          )}
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input placeholder="Biscuit 500g Pack" {...register('name')} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label>Description</Label>
            <Input placeholder="Optional" {...register('description')} />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" isLoading={isSubmitting || mutation.isPending}>
              {isEdit ? 'Save' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function SKUsPage() {
  const { hasPermission } = useAuth()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<SKUOut | undefined>()
  const [deleteTarget, setDeleteTarget] = useState<SKUOut | undefined>()

  const { data, isLoading } = useQuery({
    queryKey: ['master', 'skus', page],
    queryFn: () => masterApi.listSKUs(page),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => masterApi.deleteSKU(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'skus'] })
      toast.success('SKU deleted.')
      setDeleteTarget(undefined)
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const skus = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Layers className="h-6 w-6" /> SKUs</h1>
          <p className="text-muted-foreground text-sm">Finished goods stock-keeping units</p>
        </div>
        {hasPermission('master:write') && (
          <Button onClick={() => { setEditTarget(undefined); setDialogOpen(true) }}>
            <Plus className="h-4 w-4" /> New SKU
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Code', 'Name', 'Description', 'Created', 'Actions']}
            isLoading={isLoading}
            isEmpty={skus.length === 0}
            emptyMessage="No SKUs found."
          >
            {skus.map((s) => (
              <Tr key={s.public_id}>
                <Td className="font-mono font-medium">{s.code}</Td>
                <Td className="font-medium">{s.name}</Td>
                <Td className="text-muted-foreground max-w-xs truncate">{s.description || '—'}</Td>
                <Td className="text-muted-foreground">{formatDate(s.created_at)}</Td>
                <Td>
                  {hasPermission('master:write') && (
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setEditTarget(s); setDialogOpen(true) }}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => setDeleteTarget(s)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        </CardContent>
        {meta && (
          <Pagination page={meta.page} totalPages={meta.total_pages} total={meta.total} pageSize={meta.page_size} onPageChange={setPage} />
        )}
      </Card>

      <SKUDialog open={dialogOpen} onOpenChange={setDialogOpen} sku={editTarget} />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => !v && setDeleteTarget(undefined)}
        title="Delete SKU"
        description={`Are you sure you want to delete "${deleteTarget?.name}"?`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.public_id)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  )
}
