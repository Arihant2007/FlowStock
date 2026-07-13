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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Pagination } from '@/components/ui/pagination'
import { getErrorMessage, formatDate } from '@/lib/utils'
import { Plus, Pencil, Trash2, Warehouse } from 'lucide-react'
import type { WarehouseOut } from '@/types/api'

const createSchema = z.object({
  name: z.string().min(1, 'Name is required').max(200),
  type: z.enum(['ODS', 'RMPM'], { message: 'Select a type' }),
  description: z.string().max(1000).optional(),
})

const updateSchema = z.object({
  name: z.string().min(1).max(200).optional(),
  description: z.string().max(1000).optional(),
})

type CreateForm = z.infer<typeof createSchema>

function WarehouseDialog({
  open,
  onOpenChange,
  warehouse,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  warehouse?: WarehouseOut
}) {
  const qc = useQueryClient()
  const isEdit = !!warehouse

  const schema = isEdit ? updateSchema : createSchema
  const { register, handleSubmit, formState: { errors, isSubmitting }, setValue, reset } =
    useForm<CreateForm>({ resolver: zodResolver(schema as any) })

  const mutation = useMutation({
    mutationFn: async (data: CreateForm) => {
      if (isEdit && warehouse) {
        return masterApi.updateWarehouse(warehouse.public_id, {
          ...data,
          version: 1, // Will be updated properly in real scenario
        })
      }
      return masterApi.createWarehouse({ name: data.name, type: data.type, description: data.description ?? '' })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'warehouses'] })
      toast.success(isEdit ? 'Warehouse updated.' : 'Warehouse created.')
      onOpenChange(false)
      reset()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Warehouse' : 'Create Warehouse'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input placeholder="RMPM-Main" defaultValue={warehouse?.name} {...register('name')} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          {!isEdit && (
            <div className="space-y-1.5">
              <Label>Type</Label>
              <Select onValueChange={(v) => setValue('type', v as 'ODS' | 'RMPM')}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="RMPM">RMPM</SelectItem>
                  <SelectItem value="ODS">ODS</SelectItem>
                </SelectContent>
              </Select>
              {errors.type && <p className="text-xs text-destructive">{errors.type.message}</p>}
            </div>
          )}
          <div className="space-y-1.5">
            <Label>Description</Label>
            <Input placeholder="Optional description" defaultValue={warehouse?.description} {...register('description')} />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" isLoading={isSubmitting || mutation.isPending}>
              {isEdit ? 'Save Changes' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function WarehousesPage() {
  const { hasPermission } = useAuth()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<WarehouseOut | undefined>()
  const [deleteTarget, setDeleteTarget] = useState<WarehouseOut | undefined>()

  const { data, isLoading } = useQuery({
    queryKey: ['master', 'warehouses', page],
    queryFn: () => masterApi.listWarehouses(page),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => masterApi.deleteWarehouse(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'warehouses'] })
      toast.success('Warehouse deleted.')
      setDeleteTarget(undefined)
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const warehouses = data?.data ?? []
  const meta = data?.meta

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Warehouse className="h-6 w-6" /> Warehouses
          </h1>
          <p className="text-muted-foreground text-sm">Manage physical storage locations</p>
        </div>
        {hasPermission('master:write') && (
          <Button onClick={() => { setEditTarget(undefined); setDialogOpen(true) }}>
            <Plus className="h-4 w-4" /> New Warehouse
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Name', 'Type', 'Description', 'Created', 'Actions']}
            isLoading={isLoading}
            isEmpty={warehouses.length === 0}
            emptyMessage="No warehouses found."
          >
            {warehouses.map((wh) => (
              <Tr key={wh.public_id}>
                <Td className="font-medium">{wh.name}</Td>
                <Td>
                  <Badge
                    label={wh.type}
                    className={wh.type === 'RMPM' ? 'bg-purple-100 text-purple-800 border-purple-200' : 'bg-blue-100 text-blue-800 border-blue-200'}
                  />
                </Td>
                <Td className="text-muted-foreground max-w-xs truncate">{wh.description || '—'}</Td>
                <Td className="text-muted-foreground">{formatDate(wh.created_at)}</Td>
                <Td>
                  {hasPermission('master:write') && (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => { setEditTarget(wh); setDialogOpen(true) }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => setDeleteTarget(wh)}
                      >
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
          <Pagination
            page={meta.page}
            totalPages={meta.total_pages}
            total={meta.total}
            pageSize={meta.page_size}
            onPageChange={setPage}
          />
        )}
      </Card>

      <WarehouseDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        warehouse={editTarget}
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => !v && setDeleteTarget(undefined)}
        title="Delete Warehouse"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.public_id)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  )
}
