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

  const { data: skusData } = useQuery({
    queryKey: ['master', 'skus'],
    queryFn: () => masterApi.listSKUs(1, 100),
    enabled: hasPermission('master:read'),
  })

  const requests = requestsData?.data ?? []
  const balances = balancesData?.data ?? []
  const pendingRequests = requests.filter((r) =>
    ['SUBMITTED', 'RESERVED'].includes(r.status)
  )
  const totalMaterials = balances.length
  const lowInventory = balances.filter((b) => parseFloat(b.available_balance) < 10)

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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Pending Requests"
          value={pendingRequests.length}
          icon={Clock}
          color="bg-blue-50 text-blue-600"
          subtitle="Awaiting action"
        />
        <StatCard
          title="Active Materials"
          value={totalMaterials}
          icon={Package}
          color="bg-purple-50 text-purple-600"
          subtitle="Tracked in ledger"
        />
        <StatCard
          title="Low Inventory"
          value={lowInventory.length}
          icon={AlertCircle}
          color={lowInventory.length > 0 ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}
          subtitle="Below 10 units"
        />
        <StatCard
          title="SKUs"
          value={skusData?.data?.length ?? 0}
          icon={TrendingUp}
          color="bg-amber-50 text-amber-600"
          subtitle="Total products"
        />
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
        {hasPermission('inventory:upload') && (
          <Card className="border-green-100 bg-green-50/50 hover:bg-green-50 transition-colors cursor-pointer" onClick={() => navigate('/inventory/upload')}>
            <CardContent className="pt-6 flex items-center justify-between">
              <div>
                <p className="font-semibold text-green-900">Upload Inventory</p>
                <p className="text-sm text-green-700/70 mt-0.5">Daily RMPM snapshot</p>
              </div>
              <ArrowRight className="h-5 w-5 text-green-500" />
            </CardContent>
          </Card>
        )}
      </div>

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
