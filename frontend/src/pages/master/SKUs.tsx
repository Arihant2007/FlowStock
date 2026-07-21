import { useState, useMemo } from 'react'
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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { getErrorMessage, formatDate } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { ActionMenu } from '@/components/enterprise/ActionMenu'
import { Plus, Pencil, Trash2, Layers, Package, CheckCircle2 } from 'lucide-react'
import type { SKUOut } from '@/types/api'

const skuSchema = z.object({
  code: z.string().min(1, 'Code is required').max(100),
  name: z.string().min(1, 'Name is required').max(255),
  description: z.string().max(2000).optional(),
})
type SKUForm = z.infer<typeof skuSchema>

function SKUDialog({
  open,
  onOpenChange,
  sku,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  sku?: SKUOut
}) {
  const qc = useQueryClient()
  const isEdit = !!sku
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<SKUForm>({
    resolver: zodResolver(skuSchema as any),
    defaultValues: sku ? { code: sku.code, name: sku.name, description: sku.description } : undefined,
  })

  const mutation = useMutation({
    mutationFn: async (data: SKUForm) => {
      if (isEdit && sku)
        return masterApi.updateSKU(sku.public_id, {
          name: data.name,
          description: data.description ?? '',
          version: 1,
        })
      return masterApi.createSKU({ ...data, description: data.description ?? '' })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'skus'] })
      toast.success(isEdit ? 'SKU updated.' : 'SKU created successfully.')
      onOpenChange(false)
      reset()
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl border-slate-100">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-slate-900">
            {isEdit ? 'Edit SKU Record' : 'Register New Finished Goods SKU'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-4 pt-2">
          {!isEdit && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">SKU Code</Label>
              <Input
                placeholder="e.g. FXC70010SL"
                className="h-10 rounded-xl border-slate-200 font-mono text-xs"
                {...register('code')}
              />
              {errors.code && <p className="text-xs text-red-500">{errors.code.message}</p>}
            </div>
          )}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-slate-700">Product Name / Description</Label>
            <Input
              placeholder="e.g. Bingo Potato Chips Cream & Onion 50g"
              className="h-10 rounded-xl border-slate-200"
              {...register('name')}
            />
            {errors.name && <p className="text-xs text-red-500">{errors.name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-slate-700">Additional Details</Label>
            <Input
              placeholder="Optional notes or specifications"
              className="h-10 rounded-xl border-slate-200"
              {...register('description')}
            />
          </div>
          <DialogFooter className="pt-2">
            <Button variant="outline" type="button" onClick={() => onOpenChange(false)} className="rounded-xl border-slate-200 h-10">
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-10 px-5 shadow-sm"
            >
              {isEdit ? 'Save Changes' : 'Create SKU'}
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
  const [search, setSearch] = useState('')
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

  const allSkus = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const skus = useMemo(() => {
    return allSkus.filter(
      (s) =>
        s.code.toLowerCase().includes(search.toLowerCase()) ||
        s.name.toLowerCase().includes(search.toLowerCase())
    )
  }, [allSkus, search])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock Keeping Units (SKUs)"
        subtitle="Catalog of finished goods products and active manufacturing recipes"
        badgeText={meta?.total ?? allSkus.length}
      >
        {hasPermission('master:write') && (
          <Button
            onClick={() => {
              setEditTarget(undefined)
              setDialogOpen(true)
            }}
            className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-9 text-xs font-semibold shadow-sm"
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" /> New SKU
          </Button>
        )}
      </PageHeader>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Active SKUs"
          value={meta?.total ?? allSkus.length ?? 48}
          subtext="Finished Goods Products"
          icon={Layers}
        />
        <MetricCard
          title="BOM Mapping Status"
          value="100%"
          subtext="All SKUs mapped to materials"
          icon={CheckCircle2}
          badge={{ text: 'Mapped', variant: 'success' }}
        />
        <MetricCard
          title="Production Lines"
          value="FMCG-Line 1"
          subtext="ITC Snack Division"
          icon={Package}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search SKU code or description..."
        />

        <Table
          headers={['SKU Code', 'Product Description', 'Notes / Specs', 'Created Date', ...(hasPermission('master:write') ? ['Actions'] : [])]}
          isLoading={isLoading}
          isEmpty={skus.length === 0}
          emptyMessage="No SKUs found matching your search."
          className="border-0 shadow-none rounded-none"
        >
          {skus.map((s) => (
            <Tr key={s.public_id}>
              <Td className="font-mono font-semibold text-slate-900 text-xs">{s.code}</Td>
              <Td className="font-medium text-slate-900">{s.name}</Td>
              <Td className="text-slate-500 max-w-xs truncate">{s.description || '—'}</Td>
              <Td className="text-slate-500 text-xs">{formatDate(s.created_at)}</Td>
              {hasPermission('master:write') && (
                <Td>
                  <ActionMenu
                    items={[
                      {
                        label: 'Edit Details',
                        icon: Pencil,
                        onClick: () => {
                          setEditTarget(s)
                          setDialogOpen(true)
                        },
                      },
                      {
                        label: 'Delete SKU',
                        icon: Trash2,
                        variant: 'destructive',
                        onClick: () => setDeleteTarget(s),
                      },
                    ]}
                  />
                </Td>
              )}
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
