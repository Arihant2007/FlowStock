import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { requestsApi } from '@/api/requests'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, Tr, Td } from '@/components/ui/table'
import { getErrorMessage, formatDate, formatQty } from '@/lib/utils'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { ArrowLeft, Check, Play, PackageCheck, CheckCircle2, XCircle, ClipboardList, Layers, AlertCircle, FileSpreadsheet } from 'lucide-react'

export function RMPMRequestDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [rmpmWarehouse, setRmpmWarehouse] = useState('')
  const [approvedQtys, setApprovedQtys] = useState<Record<string, string>>({})

  const { data: requestData, isLoading } = useQuery({
    queryKey: ['requests', id],
    queryFn: () => requestsApi.getRequest(id!),
    enabled: !!id,
  })

  const { data: whData } = useQuery({
    queryKey: ['master', 'warehouses'],
    queryFn: () => masterApi.listWarehouses(1, 100),
  })

  const request = requestData?.data
  const warehouses = whData?.data ?? []
  const rmpmWarehouses = warehouses.filter((w) => w.type === 'RMPM')

  const materialSummary = useMemo(() => {
    if (!request) return []
    const map = new Map<string, any>()
    request.skus.forEach((sku: any) => {
      sku.items.forEach((item: any) => {
        const key = item.material_public_id
        if (!map.has(key)) {
          map.set(key, {
            material_public_id: item.material_public_id,
            material_name: item.material_name,
            material_code: item.material_code,
            material_type: item.material_type,
            gross_required_qty: 0,
            remaining_from_previous_day: parseFloat(item.remaining_from_previous_day),
            requested_qty: 0,
            approved_qty: 0,
            dispatched_qty: 0,
            received_qty: 0,
          })
        }
        const m = map.get(key)!
        m.gross_required_qty += parseFloat(item.gross_required_qty)
        m.requested_qty += parseFloat(item.requested_qty)
        if (item.approved_qty) m.approved_qty += parseFloat(item.approved_qty)
        if (item.dispatched_qty) m.dispatched_qty += parseFloat(item.dispatched_qty)
        if (item.received_qty) m.received_qty += parseFloat(item.received_qty)
      })
    })
    return Array.from(map.values())
  }, [request])

  useEffect(() => {
    if (materialSummary.length > 0 && Object.keys(approvedQtys).length === 0) {
      const initial: Record<string, string> = {}
      materialSummary.forEach((mat) => {
        initial[mat.material_public_id] = mat.requested_qty.toString()
      })
      setApprovedQtys(initial)
    }
  }, [materialSummary, approvedQtys])

  const actionMutation = useMutation({
    mutationFn: async ({ action, payload }: { action: string; payload?: any }) => {
      if (action === 'approve') return requestsApi.approve(id!, payload)
      if (action === 'dispatch') return requestsApi.dispatch(id!)
      if (action === 'receive') return requestsApi.receive(id!)
      if (action === 'close') return requestsApi.close(id!)
      if (action === 'reject') return requestsApi.reject(id!)
      throw new Error('Unknown action')
    },
    onSuccess: (_, { action }) => {
      qc.invalidateQueries({ queryKey: ['requests', id] })
      toast.success(`Request ${action}d successfully.`)
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const handleApprove = () => {
    if (!rmpmWarehouse) {
      toast.error('Please select source (RMPM) warehouse.')
      return
    }

    const items = Object.entries(approvedQtys).map(([matId, qty]) => ({
      material_public_id: matId,
      approved_qty: qty,
    }))

    actionMutation.mutate({
      action: 'approve',
      payload: { rmpm_warehouse_public_id: rmpmWarehouse, items },
    })
  }

  if (isLoading)
    return (
      <div className="p-12 text-center flex flex-col items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-4 border-blue-600/30 border-t-blue-600 rounded-full animate-spin mb-4" />
        <p className="text-slate-500 font-medium text-sm">Loading Request Details...</p>
      </div>
    )

  if (!request)
    return (
      <div className="p-12 text-center min-h-[50vh] flex items-center justify-center">
        <div className="p-8 max-w-md mx-auto text-center rounded-2xl bg-white border border-slate-100 shadow-sm">
          <AlertCircle className="h-12 w-12 text-slate-400 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-slate-900 mb-2">Request Not Found</h3>
          <p className="text-slate-500 text-sm mb-6">The requested material transfer ID does not exist or has been archived.</p>
          <Button onClick={() => navigate('/rmpm/requests')} className="rounded-xl">Go Back to Queue</Button>
        </div>
      </div>
    )

  const isPendingApprove = request.status === 'SUBMITTED'
  const isApproved = request.status === 'APPROVED' || request.status === 'PARTIALLY_APPROVED'
  const isDispatched = request.status === 'DISPATCHED'
  const isReceived = request.status === 'RECEIVED'

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="icon"
          onClick={() => navigate('/rmpm/requests')}
          className="rounded-xl shrink-0 h-10 w-10 border-slate-200 bg-white"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <PageHeader
          title={`Material Request #${request.public_id}`}
          subtitle={`Created for ODS production line on ${formatDate(request.request_date)}`}
        >
          <StatusBadge status={request.status} />
        </PageHeader>
      </div>

      {request.notes && (
        <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-4 flex gap-3 shadow-sm">
          <ClipboardList className="h-5 w-5 shrink-0 text-amber-700" />
          <div>
            <h4 className="font-bold text-amber-950 text-xs uppercase tracking-wider">ODS Request Notes</h4>
            <p className="text-xs text-amber-900 mt-1 font-medium">{request.notes}</p>
          </div>
        </div>
      )}

      {/* Action Control Panel */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <h3 className="font-bold text-slate-900 text-base">Approval & Fulfillment Pipeline</h3>
            <p className="text-xs text-slate-500">Advance request status or modify allocated quantities</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {isPendingApprove && (
              <Button
                size="sm"
                variant="outline"
                className="text-red-600 border-red-200 hover:bg-red-50 rounded-xl px-5 h-9 text-xs font-semibold"
                onClick={() => actionMutation.mutate({ action: 'reject' })}
                disabled={actionMutation.isPending}
              >
                <XCircle className="h-3.5 w-3.5 mr-1.5" /> Reject Request
              </Button>
            )}
            {isApproved && (
              <Button
                size="sm"
                className="rounded-xl px-5 h-9 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                onClick={() => actionMutation.mutate({ action: 'dispatch' })}
                disabled={actionMutation.isPending}
              >
                <Play className="h-3.5 w-3.5 mr-1.5" /> Mark Dispatched
              </Button>
            )}
            {isDispatched && (
              <Button
                size="sm"
                className="rounded-xl px-5 h-9 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
                onClick={() => actionMutation.mutate({ action: 'receive' })}
                disabled={actionMutation.isPending}
              >
                <PackageCheck className="h-3.5 w-3.5 mr-1.5" /> Confirm Received
              </Button>
            )}
            {isReceived && (
              <Button
                size="sm"
                variant="outline"
                className="rounded-xl px-5 h-9 text-xs font-semibold border-slate-200 text-slate-700"
                onClick={() => actionMutation.mutate({ action: 'close' })}
                disabled={actionMutation.isPending}
              >
                <CheckCircle2 className="h-3.5 w-3.5 mr-1.5 text-emerald-600" /> Close Transfer
              </Button>
            )}
          </div>
        </div>

        {isPendingApprove && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-2">
            <div className="space-y-1.5 md:col-span-2">
              <Label className="text-xs font-semibold text-slate-700">Source RMPM Warehouse</Label>
              <Select value={rmpmWarehouse} onValueChange={setRmpmWarehouse}>
                <SelectTrigger className="bg-slate-50/50 border-slate-200 rounded-xl h-10 text-xs">
                  <SelectValue placeholder="Select fulfillment warehouse..." />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  {rmpmWarehouses.map((w) => (
                    <SelectItem key={w.public_id} value={w.public_id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-1 flex items-end">
              <Button
                onClick={handleApprove}
                disabled={actionMutation.isPending || !rmpmWarehouse}
                className="w-full rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white h-10 text-xs font-semibold shadow-sm"
              >
                <Check className="h-4 w-4 mr-1.5" /> Approve & Reserve Quantities
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Aggregated Material Summary */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden space-y-2">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <Layers className="h-5 w-5 text-blue-600" /> Aggregated Material Requirements
          </h3>
          <p className="text-xs text-slate-500">Gross required vs leftover and net requested quantities</p>
        </div>

        <Table
          headers={['Material', 'Type', 'Gross Req', 'ODS Leftover', 'Net Request', isPendingApprove ? 'Approve Qty' : 'Approved', 'Status', 'Dispatched', 'Received']}
          className="border-0 shadow-none rounded-none"
        >
          {materialSummary.map((mat) => (
            <Tr key={mat.material_public_id}>
              <Td>
                <div className="font-semibold text-slate-900 text-xs">{mat.material_name}</div>
                <div className="font-mono text-[11px] text-slate-500 mt-0.5">{mat.material_code}</div>
              </Td>
              <Td>
                <StatusBadge status={mat.material_type} label={mat.material_type === 'RM' ? 'RM' : 'PM'} />
              </Td>
              <Td className="text-slate-700 font-medium text-xs">{formatQty(mat.gross_required_qty)}</Td>
              <Td className="text-amber-700 font-medium text-xs">{formatQty(mat.remaining_from_previous_day)}</Td>
              <Td className="font-bold text-blue-700 text-xs">{formatQty(mat.requested_qty)}</Td>
              <Td>
                {isPendingApprove ? (
                  <Input
                    type="number"
                    step="0.0001"
                    value={approvedQtys[mat.material_public_id] ?? ''}
                    onChange={(e) =>
                      setApprovedQtys((p) => ({ ...p, [mat.material_public_id]: e.target.value }))
                    }
                    className="w-28 h-8 rounded-lg bg-slate-50 border-slate-200 text-xs font-mono font-bold"
                  />
                ) : (
                  <span className="font-bold text-slate-900 text-xs">{formatQty(mat.approved_qty)}</span>
                )}
              </Td>
              <Td>
                {!isPendingApprove && (
                  <StatusBadge
                    status={mat.approved_qty >= mat.requested_qty ? 'NORMAL' : 'WARNING'}
                    label={mat.approved_qty >= mat.requested_qty ? 'Full' : 'Partial'}
                  />
                )}
              </Td>
              <Td className="text-blue-600 font-medium text-xs">{formatQty(mat.dispatched_qty)}</Td>
              <Td className="text-emerald-600 font-medium text-xs">{formatQty(mat.received_qty)}</Td>
            </Tr>
          ))}
        </Table>
      </div>

      {/* SKU Breakdown */}
      <div className="space-y-4">
        <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <FileSpreadsheet className="h-5 w-5 text-slate-500" /> Production Breakdown by SKU
        </h3>

        <div className="space-y-4">
          {request.skus.map((sku: any, index: number) => (
            <div key={sku.public_id} className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
              <div className="flex items-center justify-between p-4 bg-slate-50/60 border-b border-slate-100">
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">SKU #{index + 1}: {sku.sku_name || 'Production SKU'}</h4>
                </div>
                <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 border border-blue-100">
                  Plan: {formatQty(sku.planned_production_qty)} units
                </span>
              </div>

              <Table
                headers={['Material', 'Type', 'Gross Req', 'ODS Leftover', 'Net Request', 'Approved', 'Dispatched', 'Received']}
                className="border-0 shadow-none rounded-none"
              >
                {sku.items.map((item: any) => (
                  <Tr key={item.public_id}>
                    <Td className="font-medium text-slate-900 text-xs">{item.material_name}</Td>
                    <Td>
                      <StatusBadge status={item.material_type} />
                    </Td>
                    <Td className="text-xs">{formatQty(item.gross_required_qty)}</Td>
                    <Td className="text-xs text-amber-700 font-medium">{formatQty(item.remaining_from_previous_day)}</Td>
                    <Td className="text-xs font-bold text-blue-700">{formatQty(item.requested_qty)}</Td>
                    <Td className="text-xs font-semibold text-slate-900">{formatQty(item.approved_qty)}</Td>
                    <Td className="text-xs text-blue-600 font-medium">{formatQty(item.dispatched_qty)}</Td>
                    <Td className="text-xs text-emerald-600 font-medium">{formatQty(item.received_qty)}</Td>
                  </Tr>
                ))}
              </Table>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
