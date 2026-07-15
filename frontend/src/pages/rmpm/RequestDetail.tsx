import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { requestsApi } from '@/api/requests'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Table, Tr, Td } from '@/components/ui/table'
import { getErrorMessage, formatDate, formatQty } from '@/lib/utils'
import { ArrowLeft, Check, Play, PackageCheck, CheckCircle2, XCircle } from 'lucide-react'

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

  // Initialize approved quantities based on aggregated summary
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

  if (isLoading) return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading request...</div>
  if (!request) return <div className="p-8 text-center text-muted-foreground">Request not found.</div>

  const isPendingApprove = request.status === 'SUBMITTED'
  const isApproved = request.status === 'APPROVED' || request.status === 'PARTIALLY_APPROVED'
  const isDispatched = request.status === 'DISPATCHED'
  const isReceived = request.status === 'RECEIVED'

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl mx-auto pb-12">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/rmpm/requests')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">Request {request.public_id.split('-')[0]}</h1>
          <p className="text-muted-foreground text-sm">Created for {formatDate(request.request_date)}</p>
        </div>
        <div className="ml-auto">
          <Badge label={request.status} variant="status" className="text-sm px-3 py-1" />
        </div>
      </div>

      {request.notes && (
        <Card className="bg-muted/30">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground"><span className="font-semibold text-foreground">Notes:</span> {request.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* Action panel */}
      <Card className="border-primary/20 shadow-sm">
        <CardHeader className="bg-primary/5 pb-4 border-b border-primary/10 flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Workflow Actions</CardTitle>
          <div className="flex gap-2">
            {isPendingApprove && (
              <Button size="sm" variant="destructive" onClick={() => actionMutation.mutate({ action: 'reject' })} isLoading={actionMutation.isPending}>
                <XCircle className="h-4 w-4 mr-2" /> Reject
              </Button>
            )}
            {isApproved && (
              <Button size="sm" onClick={() => actionMutation.mutate({ action: 'dispatch' })} isLoading={actionMutation.isPending}>
                <Play className="h-4 w-4 mr-2" /> Mark Dispatched
              </Button>
            )}
            {isDispatched && (
              <Button size="sm" onClick={() => actionMutation.mutate({ action: 'receive' })} isLoading={actionMutation.isPending}>
                <PackageCheck className="h-4 w-4 mr-2" /> Mark Received
              </Button>
            )}
            {isReceived && (
              <Button size="sm" variant="secondary" onClick={() => actionMutation.mutate({ action: 'close' })} isLoading={actionMutation.isPending}>
                <CheckCircle2 className="h-4 w-4 mr-2" /> Close Request
              </Button>
            )}
          </div>
        </CardHeader>
        {isPendingApprove && (
          <CardContent className="pt-4 grid grid-cols-1 md:grid-cols-2 gap-4 bg-muted/10">
            <div className="space-y-1.5 md:col-span-1">
              <Label>Source Warehouse (RMPM)</Label>
              <Select value={rmpmWarehouse} onValueChange={setRmpmWarehouse}>
                <SelectTrigger><SelectValue placeholder="Select dispatch source..." /></SelectTrigger>
                <SelectContent>{rmpmWarehouses.map((w) => <SelectItem key={w.public_id} value={w.public_id}>{w.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="md:col-span-2 flex justify-end mt-2">
              <Button onClick={handleApprove} isLoading={actionMutation.isPending} disabled={!rmpmWarehouse}>
                <Check className="h-4 w-4 mr-2" /> Approve Quantities
              </Button>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Aggregated Material Summary */}
      <Card>
        <CardHeader className="bg-primary/5 pb-3">
          <CardTitle className="text-base">Aggregated Material Summary</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 px-0">
          <Table headers={['Material', 'Type', 'Gross Req', 'Leftover', 'Net Request', isPendingApprove ? 'Approve Qty' : 'Approved', 'Dispatched', 'Received']}>
            {materialSummary.map((mat) => (
              <Tr key={mat.material_public_id}>
                <Td>
                  <div className="font-medium">{mat.material_name}</div>
                  <div className="text-xs text-muted-foreground">{mat.material_code}</div>
                </Td>
                <Td><Badge label={mat.material_type} variant={mat.material_type.toLowerCase() as any} /></Td>
                <Td className="font-mono text-sm">{formatQty(mat.gross_required_qty)}</Td>
                <Td className="font-mono text-sm text-orange-600">{formatQty(mat.remaining_from_previous_day)}</Td>
                <Td className="font-mono text-sm font-semibold">{formatQty(mat.requested_qty)}</Td>
                <Td>
                  {isPendingApprove ? (
                    <div className="w-32">
                      <Input
                        type="number"
                        step="0.0001"
                        value={approvedQtys[mat.material_public_id] ?? ''}
                        onChange={(e) => setApprovedQtys((p) => ({ ...p, [mat.material_public_id]: e.target.value }))}
                      />
                    </div>
                  ) : (
                    <span className="font-mono text-sm font-bold text-primary">{mat.approved_qty ? formatQty(mat.approved_qty) : '-'}</span>
                  )}
                </Td>
                <Td className="font-mono text-sm text-blue-600">{mat.dispatched_qty ? formatQty(mat.dispatched_qty) : '-'}</Td>
                <Td className="font-mono text-sm text-green-600">{mat.received_qty ? formatQty(mat.received_qty) : '-'}</Td>
              </Tr>
            ))}
          </Table>
        </CardContent>
      </Card>

      {/* SKU Breakdown (Requested Items) */}
      <div className="space-y-6">
        {request.skus.map((sku, index) => (
          <Card key={sku.public_id}>
            <CardHeader className="bg-muted/30 pb-3">
              <CardTitle className="text-base flex items-center justify-between">
                <span>SKU #{index + 1}</span>
                <Badge label={`Plan: ${formatQty(sku.planned_production_qty)} units`} variant="default" />
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 px-0">
              <Table headers={['Material', 'Type', 'Gross Req', 'Leftover', 'Net Request', 'Approved', 'Dispatched', 'Received']}>
                {sku.items.map((item) => (
                  <Tr key={item.public_id}>
                    <Td>
                      <div className="font-medium">{item.material_name}</div>
                      <div className="text-xs text-muted-foreground">{item.material_code}</div>
                    </Td>
                    <Td><Badge label={item.material_type} variant={item.material_type.toLowerCase() as any} /></Td>
                    <Td className="font-mono text-sm">{formatQty(item.gross_required_qty)}</Td>
                    <Td className="font-mono text-sm text-orange-600">{formatQty(item.remaining_from_previous_day)}</Td>
                    <Td className="font-mono text-sm font-semibold">{formatQty(item.requested_qty)}</Td>
                    <Td>
                      {isPendingApprove ? (
                        <span className="text-xs text-muted-foreground italic">Auto-allocated</span>
                      ) : (
                        <span className="font-mono text-sm font-bold text-primary">{item.approved_qty ? formatQty(item.approved_qty) : '-'}</span>
                      )}
                    </Td>
                    <Td className="font-mono text-sm text-blue-600">{item.dispatched_qty ? formatQty(item.dispatched_qty) : '-'}</Td>
                    <Td className="font-mono text-sm text-green-600">{item.received_qty ? formatQty(item.received_qty) : '-'}</Td>
                  </Tr>
                ))}
              </Table>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
