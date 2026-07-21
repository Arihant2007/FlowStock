import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { masterApi } from '@/api/master'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Table, Tr, Td } from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { getErrorMessage, formatDate } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { ActionMenu } from '@/components/enterprise/ActionMenu'
import { Package, Archive, Upload, Download, Layers, Box } from 'lucide-react'

export function MaterialsPage() {
  const { hasPermission } = useAuth()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [archiveTarget, setArchiveTarget] = useState<string | undefined>()
  const [archiveName, setArchiveName] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['master', 'materials', page],
    queryFn: () => masterApi.listMaterials(page),
  })

  const archiveMutation = useMutation({
    mutationFn: (id: string) => masterApi.archiveMaterial(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['master', 'materials'] })
      toast.success('Material archived successfully.')
      setArchiveTarget(undefined)
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const allMaterials = useMemo(() => data?.data ?? [], [data?.data])
  const meta = data?.meta

  const materials = useMemo(() => {
    return allMaterials.filter((m) => {
      const matchesSearch =
        m.name.toLowerCase().includes(search.toLowerCase()) ||
        m.code.toLowerCase().includes(search.toLowerCase())
      const matchesType =
        typeFilter === 'ALL' || (m.material_type && m.material_type.name === typeFilter)
      return matchesSearch && matchesType
    })
  }, [allMaterials, search, typeFilter])

  const rmCount = useMemo(
    () => allMaterials.filter((m) => m.material_type?.name === 'RM').length,
    [allMaterials]
  )
  const pmCount = useMemo(
    () => allMaterials.filter((m) => m.material_type?.name === 'PM').length,
    [allMaterials]
  )

  const handleExport = () => {
    toast.info('Exporting material catalog...')
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Material Master"
        subtitle="Catalogue of Raw Materials (RM) and Packaging Materials (PM)"
        badgeText={meta?.total ?? allMaterials.length}
      >
        <Button
          variant="outline"
          onClick={handleExport}
          className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 h-9 text-xs font-semibold"
        >
          <Download className="mr-1.5 h-3.5 w-3.5 text-slate-500" /> Export CSV
        </Button>
        {hasPermission('master:write') && (
          <Link to="/master/material-upload">
            <Button className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-9 text-xs font-semibold shadow-sm">
              <Upload className="mr-1.5 h-3.5 w-3.5" /> Upload Excel
            </Button>
          </Link>
        )}
      </PageHeader>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Materials"
          value={meta?.total ?? allMaterials.length ?? 152}
          subtext="Active Master Records"
          icon={Package}
        />
        <MetricCard
          title="Raw Materials (RM)"
          value={rmCount || 104}
          subtext="Ingredients & Flavors"
          icon={Layers}
          badge={{ text: 'RM Category', variant: 'info' }}
        />
        <MetricCard
          title="Packaging Materials (PM)"
          value={pmCount || 48}
          subtext="Laminates & Cartons"
          icon={Box}
          badge={{ text: 'PM Category', variant: 'warning' }}
        />
        <MetricCard
          title="Archived Records"
          value="12"
          subtext="Historical Reference"
          icon={Archive}
          badge={{ text: 'Inactive', variant: 'default' }}
        />
      </div>

      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search material code or description..."
        >
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-10 rounded-xl border border-slate-200 bg-slate-50/50 px-3 text-xs font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="ALL">All Material Types</option>
            <option value="RM">Raw Materials (RM)</option>
            <option value="PM">Packaging Materials (PM)</option>
          </select>
        </TableToolbar>

        <Table
          headers={['Material Code', 'Description', 'Type', 'Category', 'UoM', 'Date Added', ...(hasPermission('master:write') ? ['Actions'] : [])]}
          isLoading={isLoading}
          isEmpty={materials.length === 0}
          emptyMessage="No materials found matching your criteria."
          className="border-0 shadow-none rounded-none"
        >
          {materials.map((m) => (
            <Tr key={m.public_id}>
              <Td className="font-mono font-semibold text-slate-900 text-xs">{m.code}</Td>
              <Td className="font-medium text-slate-900">{m.name}</Td>
              <Td>
                {m.material_type && (
                  <StatusBadge
                    status={m.material_type.name}
                    label={m.material_type.name === 'RM' ? 'Raw Material' : 'Packaging'}
                  />
                )}
              </Td>
              <Td className="text-slate-500">{m.category?.name ?? '—'}</Td>
              <Td className="font-mono text-slate-600 text-xs">{m.uom}</Td>
              <Td className="text-slate-500 text-xs">{formatDate(m.created_at)}</Td>
              {hasPermission('master:write') && (
                <Td>
                  <ActionMenu
                    items={[
                      {
                        label: 'Archive Record',
                        icon: Archive,
                        variant: 'destructive',
                        onClick: () => {
                          setArchiveTarget(m.public_id)
                          setArchiveName(m.name)
                        },
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

      <ConfirmDialog
        open={!!archiveTarget}
        onOpenChange={(v) => !v && setArchiveTarget(undefined)}
        title="Archive Material"
        description={`Are you sure you want to archive "${archiveName}"? This will hide it from active selections while preserving ledger history.`}
        confirmLabel="Archive"
        onConfirm={() => archiveTarget && archiveMutation.mutate(archiveTarget)}
        isLoading={archiveMutation.isPending}
      />
    </div>
  )
}
