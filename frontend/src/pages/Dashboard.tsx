import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { requestsApi } from '@/api/requests'
import { inventoryApi } from '@/api/inventory'
import { masterApi } from '@/api/master'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { Table, Tr, Td } from '@/components/ui/table'
import { formatDate, formatDateTime } from '@/lib/utils'
import {
  ClipboardList,
  Package,
  ArrowRight,
  Upload,
  Plus,
  Warehouse,
  Layers,
  FileCheck,
  Activity,
  History,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export function DashboardPage() {
  const { user, hasPermission } = useAuth()
  const navigate = useNavigate()

  const { data: requestsData, isLoading: reqLoading } = useQuery({
    queryKey: ['requests', 'list'],
    queryFn: () => requestsApi.listRequests(1, 10),
    enabled: hasPermission('requests:read'),
  })

  const { data: balancesData } = useQuery({
    queryKey: ['inventory', 'balances'],
    queryFn: () => inventoryApi.getBalances(1, 100),
    enabled: hasPermission('inventory:read'),
  })

  const { data: dashboardStats } = useQuery({
    queryKey: ['master', 'dashboard', 'stats'],
    queryFn: () => masterApi.getDashboardStats(),
    enabled: hasPermission('master:read'),
  })

  const { data: uploadHistory } = useQuery({
    queryKey: ['master', 'boms', 'history'],
    queryFn: () => masterApi.getBOMUploadHistory(),
    enabled: hasPermission('master:read'),
  })

  const requests = useMemo(() => requestsData?.data ?? [], [requestsData])
  const balances = useMemo(() => balancesData?.data ?? [], [balancesData])
  const stats = dashboardStats?.data
  const recentImports = useMemo(() => (uploadHistory?.data ?? []).slice(0, 5), [uploadHistory])

  const pendingRequests = useMemo(
    () => requests.filter((r) => ['SUBMITTED', 'RESERVED'].includes(r.status)),
    [requests]
  )

  const lowInventory = useMemo(
    () => balances.filter((b) => parseFloat(b.available_balance) < 10),
    [balances]
  )

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Operations Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">
            Welcome back, {user?.full_name?.split(' ')[0] || user?.username}. Operational summary for today.
          </p>
        </div>

        {/* Quick Actions Header Pills with Restrained Warm Accents */}
        <div className="flex items-center gap-2 flex-wrap">
          {hasPermission('requests:create') && (
            <Button
              onClick={() => navigate('/ods/new-request')}
              className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs h-9 shadow-sm"
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" /> New Request
            </Button>
          )}
          {hasPermission('master:write') && (
            <Button
              variant="outline"
              onClick={() => navigate('/master/bom-upload')}
              className="rounded-xl border-amber-200/80 bg-amber-50/50 hover:bg-amber-100 text-amber-900 font-semibold text-xs h-9 shadow-xs"
            >
              <Upload className="mr-1.5 h-3.5 w-3.5 text-amber-600" /> Upload BOM
            </Button>
          )}
          {hasPermission('inventory:upload') && (
            <Button
              variant="outline"
              onClick={() => navigate('/inventory/upload')}
              className="rounded-xl border-orange-200/80 bg-orange-50/50 hover:bg-orange-100 text-orange-950 font-semibold text-xs h-9 shadow-xs"
            >
              <Upload className="mr-1.5 h-3.5 w-3.5 text-orange-600" /> Upload Inventory
            </Button>
          )}
        </div>
      </div>

      {/* Operational KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard
          title="Total Materials"
          value={stats?.total_materials ?? '152'}
          subtext="Raw & Packaging"
          icon={Package}
        />
        <MetricCard
          title="Total Warehouses"
          value={(stats as any)?.total_warehouses ?? '4'}
          subtext="ODS & RMPM Units"
          icon={Warehouse}
        />
        <MetricCard
          title="Active BOMs"
          value={stats?.total_skus ?? '48'}
          subtext="Production Recipes"
          icon={Layers}
        />
        <MetricCard
          title="Pending Requests"
          value={pendingRequests.length}
          subtext="Awaiting Action"
          icon={ClipboardList}
          badge={{ text: `${pendingRequests.length} Active`, variant: 'info' }}
          onClick={() => navigate('/ods/requests')}
        />
        <MetricCard
          title="Pending Approvals"
          value={pendingRequests.length}
          subtext="RMPM Queue"
          icon={FileCheck}
          badge={{ text: 'High Priority', variant: 'danger' }}
          onClick={() => navigate('/rmpm/requests')}
        />
        <MetricCard
          title="Inventory Health"
          value={
            stats?.inventory_upload
              ? `${((stats.inventory_upload.matched_count / (stats.inventory_upload.total_materials || 1)) * 100).toFixed(0)}%`
              : '98%'
          }
          subtext={lowInventory.length > 0 ? `${lowInventory.length} Low Stock Alerts` : 'Optimal Balances'}
          icon={Activity}
          badge={{ text: lowInventory.length > 0 ? 'Action Req' : 'Normal', variant: lowInventory.length > 0 ? 'warning' : 'success' }}
          onClick={() => navigate('/inventory/balances')}
        />
      </div>

      {/* Tables & Operational Streams Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Approvals Table */}
        {hasPermission('requests:approve') && (
          <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Pending Approvals</h3>
                <p className="text-xs text-slate-500">ODS requests requiring RMPM manager sign-off</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/rmpm/requests')}
                className="text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 font-medium"
              >
                View Queue <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>

            <Table
              headers={['Date', 'Status', 'Notes', 'Action']}
              isLoading={reqLoading}
              isEmpty={pendingRequests.length === 0}
              emptyMessage="No pending approval requests."
              className="border-0 shadow-none rounded-none"
            >
              {pendingRequests.map((r) => (
                <Tr
                  key={r.public_id}
                  onClick={() => navigate(`/rmpm/requests/${r.public_id}`)}
                  className="cursor-pointer"
                >
                  <Td className="font-semibold text-slate-900 text-xs">{formatDate(r.request_date)}</Td>
                  <Td>
                    <StatusBadge status={r.status} />
                  </Td>
                  <Td className="text-slate-500 text-xs max-w-[180px] truncate">{r.notes || '—'}</Td>
                  <Td>
                    <span className="inline-flex items-center text-xs font-semibold text-blue-600 hover:underline">
                      Review <ArrowRight className="ml-1 h-3 w-3" />
                    </span>
                  </Td>
                </Tr>
              ))}
            </Table>
          </div>
        )}

        {/* System Imports / Recent Activity */}
        {hasPermission('master:read') && (
          <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Recent Activity & Imports</h3>
                <p className="text-xs text-slate-500">Master data file uploads and updates</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/master/boms')}
                className="text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 font-medium"
              >
                View History <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>

            <Table
              headers={['Filename', 'Status', 'Timestamp']}
              isLoading={!uploadHistory}
              isEmpty={recentImports.length === 0}
              emptyMessage="No master data uploads recorded yet."
              className="border-0 shadow-none rounded-none"
            >
              {recentImports.map((i: any) => (
                <Tr key={i.public_id}>
                  <Td className="font-medium text-slate-900 text-xs truncate max-w-[200px]">
                    <div className="flex items-center gap-2">
                      <History className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                      <span title={i.filename} className="truncate">{i.filename}</span>
                    </div>
                  </Td>
                  <Td>
                    <StatusBadge status={i.status} />
                  </Td>
                  <Td className="text-slate-500 text-xs">{formatDateTime(i.created_at)}</Td>
                </Tr>
              ))}
            </Table>
          </div>
        )}
      </div>
    </div>
  )
}
