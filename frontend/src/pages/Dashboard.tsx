import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { requestsApi } from '@/api/requests'
import { inventoryApi } from '@/api/inventory'
import { masterApi } from '@/api/master'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, Tr, Td } from '@/components/ui/table'
import { formatDate, formatDateTime } from '@/lib/utils'
import {
  ClipboardList,
  TrendingUp,
  Package,
  ArrowRight,
  AlertCircle,
  Clock,
  Upload,
  CheckCircle,
} from 'lucide-react'

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  color: string
  subtitle?: string
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold mt-1">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
          </div>
          <div className={`h-12 w-12 rounded-xl flex items-center justify-center ${color}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

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

  const requests = requestsData?.data ?? []
  const balances = balancesData?.data ?? []
  const pendingRequests = requests.filter((r) =>
    ['SUBMITTED', 'RESERVED'].includes(r.status)
  )
  const lowInventory = balances.filter((b) => parseFloat(b.available_balance) < 10)
  
  const stats = dashboardStats?.data
  const recentImports = (uploadHistory?.data ?? []).slice(0, 5)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Good{' '}
          {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}
          , {user?.full_name?.split(' ')[0]}.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Materials"
          value={stats?.total_materials ?? 0}
          icon={Package}
          color="bg-purple-50 text-purple-600"
          subtitle="Total raw & packaging"
        />
        <StatCard
          title="SKUs"
          value={stats?.total_skus ?? 0}
          icon={TrendingUp}
          color="bg-amber-50 text-amber-600"
          subtitle="Finished goods"
        />
        <StatCard
          title="BOM Versions"
          value={stats?.total_bom_versions ?? 0}
          icon={ClipboardList}
          color="bg-blue-50 text-blue-600"
          subtitle="Active recipes"
        />
        <StatCard
          title="Low Inventory"
          value={lowInventory.length}
          icon={AlertCircle}
          color={lowInventory.length > 0 ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}
          subtitle="Below 10 units"
        />
        
        {/* Inventory Health KPI */}
        {hasPermission('inventory:read') && stats?.inventory_upload && (
          <StatCard
            title="Inventory Health"
            value={`${stats.inventory_upload.total_materials > 0 ? ((stats.inventory_upload.matched_count / stats.inventory_upload.total_materials) * 100).toFixed(1) : 0}%`}
            icon={CheckCircle}
            color="bg-emerald-50 text-emerald-600"
            subtitle={`${stats.inventory_upload.variance_count} variances`}
          />
        )}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {hasPermission('requests:create') && (
          <Card className="border-blue-100 bg-blue-50/50 hover:bg-blue-50 transition-colors cursor-pointer" onClick={() => navigate('/ods/new-request')}>
            <CardContent className="pt-6 flex items-center justify-between">
              <div>
                <p className="font-semibold text-blue-900">New Morning Request</p>
                <p className="text-sm text-blue-700/70 mt-0.5">Submit material request for ODS</p>
              </div>
              <ArrowRight className="h-5 w-5 text-blue-500" />
            </CardContent>
          </Card>
        )}
        {hasPermission('requests:approve') && (
          <Card className="border-amber-100 bg-amber-50/50 hover:bg-amber-50 transition-colors cursor-pointer" onClick={() => navigate('/rmpm/requests')}>
            <CardContent className="pt-6 flex items-center justify-between">
              <div>
                <p className="font-semibold text-amber-900">Review Requests</p>
                <p className="text-sm text-amber-700/70 mt-0.5">{pendingRequests.length} pending approval</p>
              </div>
              <ArrowRight className="h-5 w-5 text-amber-500" />
            </CardContent>
          </Card>
        )}
        {hasPermission('master:write') && (
          <Card className="border-indigo-100 bg-indigo-50/50 hover:bg-indigo-50 transition-colors cursor-pointer" onClick={() => navigate('/master/boms/upload')}>
            <CardContent className="pt-6 flex items-center justify-between">
              <div>
                <p className="font-semibold text-indigo-900">Upload BOM</p>
                <p className="text-sm text-indigo-700/70 mt-0.5">Import recipes from Excel</p>
              </div>
              <ArrowRight className="h-5 w-5 text-indigo-500" />
            </CardContent>
          </Card>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent requests */}
        {hasPermission('requests:read') && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ClipboardList className="h-4 w-4" />
                Recent Requests
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate(hasPermission('requests:approve') ? '/rmpm/requests' : '/ods/requests')}>
                View all <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </CardHeader>
            <CardContent className="pt-0">
              <Table
                headers={['Date', 'Status', 'Notes', 'Created']}
                isLoading={reqLoading}
                isEmpty={requests.length === 0}
                emptyMessage="No requests yet."
              >
                {requests.map((r) => (
                  <Tr key={r.public_id} onClick={() => navigate(hasPermission('requests:approve') ? `/rmpm/requests/${r.public_id}` : '/ods/requests')}>
                    <Td>{formatDate(r.request_date)}</Td>
                    <Td><Badge label={r.status} variant="status" /></Td>
                    <Td className="text-muted-foreground max-w-xs truncate">{r.notes || '—'}</Td>
                    <Td className="text-muted-foreground">{formatDateTime(r.created_at)}</Td>
                  </Tr>
                ))}
              </Table>
            </CardContent>
          </Card>
        )}

        {/* Recent BOM Imports */}
        {hasPermission('master:read') && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Upload className="h-4 w-4" />
                Recent Master Data Imports
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/master/boms')}>
                View all <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </CardHeader>
            <CardContent className="pt-0">
              <Table
                headers={['Filename', 'Status', 'Date', 'SKUs Created']}
                isLoading={!uploadHistory}
                isEmpty={recentImports.length === 0}
                emptyMessage="No imports yet."
              >
                {recentImports.map((i: any) => (
                  <Tr key={i.public_id}>
                    <Td className="font-medium truncate max-w-[150px]" title={i.filename}>{i.filename}</Td>
                    <Td><Badge label={i.status} variant="status" /></Td>
                    <Td className="text-muted-foreground">{formatDateTime(i.created_at)}</Td>
                    <Td className="text-right">
                      {i.import_results?.skus_created ?? '—'}
                    </Td>
                  </Tr>
                ))}
              </Table>
            </CardContent>
          </Card>
        )}
        
        {/* Inventory Upload Details */}
        {hasPermission('inventory:read') && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Package className="h-4 w-4" />
                Latest Inventory Snapshot
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/inventory/upload')}>
                Upload New <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </CardHeader>
            <CardContent className="pt-0">
              {stats?.inventory_upload ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Business Date</p>
                      <p className="text-lg font-semibold">{formatDate(stats.inventory_upload.snapshot_date)}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Warehouse</p>
                      <p className="text-lg font-semibold truncate" title={stats.inventory_upload.warehouse_name ?? 'Unknown'}>{stats.inventory_upload.warehouse_name}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Version</p>
                      <p className="text-lg font-semibold">v{stats.inventory_upload.version}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Total Materials</p>
                      <p className="text-sm">{stats.inventory_upload.total_materials}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Uploaded By</p>
                      <p className="text-sm">{stats.inventory_upload.uploaded_by}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-muted-foreground">Upload Timestamp</p>
                      <p className="text-sm">{formatDateTime(stats.inventory_upload.upload_time)}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6 text-muted-foreground">
                  <p>No inventory snapshot uploaded yet.</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Low inventory alert */}
      {hasPermission('inventory:read') && lowInventory.length > 0 && (
        <Card className="border-red-200 bg-red-50/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-red-700 flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              Low Inventory Alert
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <Table headers={['Material', 'Warehouse', 'Available', 'UoM']} isEmpty={false}>
              {lowInventory.map((b) => (
                <Tr key={`${b.material_public_id}-${b.warehouse_public_id}`}>
                  <Td>
                    <div>
                      <p className="font-medium">{b.material_name}</p>
                      <p className="text-xs text-muted-foreground">{b.material_code}</p>
                    </div>
                  </Td>
                  <Td>{b.warehouse_name}</Td>
                  <Td className="text-red-700 font-semibold">{b.available_balance}</Td>
                  <Td>{b.uom}</Td>
                </Tr>
              ))}
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
