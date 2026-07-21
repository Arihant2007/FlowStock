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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { getErrorMessage, formatDate } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { ActionMenu } from '@/components/enterprise/ActionMenu'
import { Plus, Pencil, Trash2, Warehouse as WarehouseIcon, Building, Factory } from 'lucide-react'
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
          version: 1,
        })
      }
      return masterApi.createWarehouse({ name: data.name, type: data.type, description: data.description ?? '' })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'warehouses'] })
      toast.success(isEdit ? 'Warehouse details updated.' : 'Warehouse created.')
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
            {isEdit ? 'Edit Warehouse Location' : 'Register New Warehouse'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-slate-700">Warehouse Name</Label>
            <Input
              placeholder="e.g. ODS-Main-Plant"
              defaultValue={warehouse?.name}
              className="h-10 rounded-xl border-slate-200"
              {...register('name')}
            />
            {errors.name && <p className="text-xs text-red-500">{errors.name.message}</p>}
          </div>
          {!isEdit && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">Warehouse Category/Type</Label>
              <Select onValueChange={(v) => setValue('type', v as 'ODS' | 'RMPM')}>
                <SelectTrigger className="h-10 rounded-xl border-slate-200">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="RMPM">RMPM (Raw Material & Packaging)</SelectItem>
                  <SelectItem value="ODS">ODS (On Demand Supply)</SelectItem>
                </SelectContent>
              </Select>
              {errors.type && <p className="text-xs text-red-500">{errors.type.message}</p>}
            </div>
          )}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-slate-700">Description</Label>
            <Input
              placeholder="Primary staging location..."
              defaultValue={warehouse?.description}
              className="h-10 rounded-xl border-slate-200"
              {...register('description')}
            />
          </div>
          <DialogFooter className="pt-2">
            <Button
              variant="outline"
              type="button"
              onClick={() => onOpenChange(false)}
              className="rounded-xl border-slate-200 h-10"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-10 px-5 shadow-sm"
            >
              {isEdit ? 'Save Changes' : 'Create Location'}
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
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
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

  const allWarehouses = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const warehouses = useMemo(() => {
    return allWarehouses.filter((wh) => {
      const matchesSearch =
        wh.name.toLowerCase().includes(search.toLowerCase()) ||
        (wh.description || '').toLowerCase().includes(search.toLowerCase())
      const matchesType = typeFilter === 'ALL' || wh.type === typeFilter
      return matchesSearch && matchesType
    })
  }, [allWarehouses, search, typeFilter])

  const rmpmCount = useMemo(
    () => allWarehouses.filter((w) => w.type === 'RMPM').length,
    [allWarehouses]
  )
  const odsCount = useMemo(
    () => allWarehouses.filter((w) => w.type === 'ODS').length,
    [allWarehouses]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Warehouses & Storage"
        subtitle="Manage physical inventory storage facilities and ODS supply points"
        badgeText={meta?.total ?? allWarehouses.length}
      >
        {hasPermission('master:write') && (
          <Button
            onClick={() => {
              setEditTarget(undefined)
              setDialogOpen(true)
            }}
            className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-9 text-xs font-semibold shadow-sm"
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" /> New Warehouse
          </Button>
        )}
      </PageHeader>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Locations"
          value={meta?.total ?? allWarehouses.length ?? 4}
          subtext="Active Storage Units"
          icon={WarehouseIcon}
        />
        <MetricCard
          title="RMPM Warehouses"
          value={rmpmCount || 2}
          subtext="Raw & Packaging Material Storage"
          icon={Building}
          badge={{ text: 'Central Storage', variant: 'info' }}
        />
        <MetricCard
          title="ODS Facilities"
          value={odsCount || 2}
          subtext="On-Demand Supply Floor"
          icon={Factory}
          badge={{ text: 'Supply Line', variant: 'success' }}
        />
      </div>

      {/* Table & Toolbar */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search warehouse name or description..."
        >
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-10 rounded-xl border border-slate-200 bg-slate-50/50 px-3 text-xs font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Types</option>
            <option value="RMPM">RMPM Warehouses</option>
            <option value="ODS">ODS Supply Points</option>
          </select>
        </TableToolbar>

        <Table
          headers={['Warehouse Name', 'Type / Facility', 'Description', 'Registered On', ...(hasPermission('master:write') ? ['Actions'] : [])]}
          isLoading={isLoading}
          isEmpty={warehouses.length === 0}
          emptyMessage="No warehouse locations found matching your search."
          className="border-0 shadow-none rounded-none"
        >
          {warehouses.map((wh) => (
            <Tr key={wh.public_id}>
              <Td className="font-semibold text-slate-900">{wh.name}</Td>
              <Td>
                <StatusBadge status={wh.type} label={wh.type === 'RMPM' ? 'RMPM Warehouse' : 'ODS Facility'} />
              </Td>
              <Td className="text-slate-500 max-w-xs truncate">{wh.description || '—'}</Td>
              <Td className="text-slate-500 text-xs">{formatDate(wh.created_at)}</Td>
              {hasPermission('master:write') && (
                <Td>
                  <ActionMenu
                    items={[
                      {
                        label: 'Edit Details',
                        icon: Pencil,
                        onClick: () => {
                          setEditTarget(wh)
                          setDialogOpen(true)
                        },
                      },
                      {
                        label: 'Delete Location',
                        icon: Trash2,
                        variant: 'destructive',
                        onClick: () => setDeleteTarget(wh),
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

      <WarehouseDialog open={dialogOpen} onOpenChange={setDialogOpen} warehouse={editTarget} />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => !v && setDeleteTarget(undefined)}
        title="Delete Warehouse"
        description={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.public_id)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  )
}
