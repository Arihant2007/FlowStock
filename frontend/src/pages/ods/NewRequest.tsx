import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { requestsApi } from '@/api/requests'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getErrorMessage } from '@/lib/utils'
import { ClipboardList, Plus, Trash2, Eye, CheckCircle } from 'lucide-react'
import type { RequestPreviewOut } from '@/types/api'
import { Table, Tr, Td } from '@/components/ui/table'

const skuInputSchema = z.object({
  sku_public_id: z.string().min(1, 'Select a SKU'),
  planned_production_qty: z.string().refine(v => !isNaN(Number(v)) && Number(v) > 0, 'Must be > 0'),
})

const requestSchema = z.object({
  request_date: z.string().min(1, 'Date is required'),
  ods_warehouse_public_id: z.string().min(1, 'Warehouse is required'),
  notes: z.string().optional().default(''),
  skus: z.array(skuInputSchema).min(1, 'Add at least one SKU'),
})

type RequestForm = z.infer<typeof requestSchema>

export function NewRequestPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const today = format(new Date(), 'yyyy-MM-dd')

  const [previewData, setPreviewData] = useState<RequestPreviewOut | null>(null)

  const { data: skusData } = useQuery({
    queryKey: ['master', 'skus'],
    queryFn: () => masterApi.listSKUs(1, 1000),
  })

  const { data: warehousesData } = useQuery({
    queryKey: ['master', 'warehouses'],
    queryFn: () => masterApi.listWarehouses(1, 100),
  })

  const odsWarehouses = useMemo(() => {
    return warehousesData?.data?.filter(w => w.type === 'ODS') || []
  }, [warehousesData])

  const { register, control, handleSubmit, watch, setValue, formState: { errors } } = useForm<RequestForm>({
    resolver: zodResolver(requestSchema as any),
    defaultValues: { request_date: today, notes: '', skus: [], ods_warehouse_public_id: '' },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'skus' })

  // Auto-select first ODS warehouse if available
  const watchWarehouse = watch('ods_warehouse_public_id')
  if (!watchWarehouse && odsWarehouses.length > 0) {
    setValue('ods_warehouse_public_id', odsWarehouses[0].public_id)
  }

  const previewMutation = useMutation({
    mutationFn: (data: RequestForm) => requestsApi.previewRequest(data),
    onSuccess: (res) => {
      setPreviewData(res.data)
      toast.success('Preview generated successfully.')
    },
    onError: (err) => {
      setPreviewData(null)
      toast.error(getErrorMessage(err))
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: RequestForm) => requestsApi.createRequest(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['requests'] })
      toast.success('Morning request submitted successfully.')
      navigate('/ods/requests')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const skus = skusData?.data ?? []

  const handlePreview = handleSubmit((d) => previewMutation.mutate(d))
  const handleSubmitFinal = handleSubmit((d) => createMutation.mutate(d))

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl mx-auto pb-12">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ClipboardList className="h-6 w-6" /> New Morning Request
        </h1>
        <p className="text-muted-foreground text-sm">Submit planned production quantities.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <CardHeader className="pb-4">
              <CardTitle className="text-base">Request Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Request Date</Label>
                <Input type="date" {...register('request_date')} onChange={() => setPreviewData(null)} />
                {errors.request_date && <p className="text-xs text-destructive">{errors.request_date.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>ODS Warehouse</Label>
                <Select value={watchWarehouse} onValueChange={(v) => { setValue('ods_warehouse_public_id', v); setPreviewData(null) }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select ODS Warehouse" />
                  </SelectTrigger>
                  <SelectContent>
                    {odsWarehouses.map((w) => (
                      <SelectItem key={w.public_id} value={w.public_id}>{w.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.ods_warehouse_public_id && <p className="text-xs text-destructive">{errors.ods_warehouse_public_id.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>Notes (Optional)</Label>
                <Input placeholder="E.g. Extra production" {...register('notes')} />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="pb-4 flex flex-row items-center justify-between border-b">
              <CardTitle className="text-base">Production Plan</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => { append({ sku_public_id: '', planned_production_qty: '' }); setPreviewData(null) }}>
                <Plus className="h-4 w-4 mr-1" /> Add SKU
              </Button>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {fields.length === 0 && (
                <div className="text-center py-8 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                  No SKUs added yet.
                </div>
              )}

              {fields.map((field, index) => (
                <div key={field.id} className="flex gap-4 items-start p-4 bg-slate-50 border rounded-lg">
                  <div className="flex-1 space-y-1.5">
                    <Label>Finished Good (SKU)</Label>
                    <Select value={watch(`skus.${index}.sku_public_id`)} onValueChange={(v) => { setValue(`skus.${index}.sku_public_id`, v); setPreviewData(null) }}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select SKU..." />
                      </SelectTrigger>
                      <SelectContent>
                        {skus.map((s) => (
                          <SelectItem key={s.public_id} value={s.public_id}>{s.name} ({s.code})</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.skus?.[index]?.sku_public_id && <p className="text-xs text-destructive">{errors.skus[index]?.sku_public_id?.message}</p>}
                  </div>
                  <div className="w-32 space-y-1.5">
                    <Label>Plan Qty</Label>
                    <Input placeholder="Qty" {...register(`skus.${index}.planned_production_qty`)} onChange={(e) => { register(`skus.${index}.planned_production_qty`).onChange(e); setPreviewData(null) }} />
                    {errors.skus?.[index]?.planned_production_qty && <p className="text-xs text-destructive">{errors.skus[index]?.planned_production_qty?.message}</p>}
                  </div>
                  <Button type="button" variant="ghost" size="icon" className="mt-6 text-destructive hover:bg-destructive/10" onClick={() => { remove(index); setPreviewData(null) }}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              {errors.skus?.root && <p className="text-sm text-destructive">{errors.skus.root.message}</p>}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex justify-end gap-4">
        <Button type="button" variant="outline" onClick={() => navigate('/ods/requests')}>Cancel</Button>
        <Button type="button" onClick={handlePreview} isLoading={previewMutation.isPending}>
          <Eye className="h-4 w-4 mr-2" /> Preview Request
        </Button>
      </div>

      {previewData && (
        <Card className="border-green-200 bg-green-50/20 animate-in slide-in-from-bottom-4">
          <CardHeader className="border-b border-green-100 pb-4">
            <CardTitle className="text-lg text-green-900 flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" /> Preview Results
            </CardTitle>
            <CardDescription>
              Review the calculated material requirements before submitting.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6 space-y-8">
            {previewData.skus.map((sku) => (
              <div key={sku.sku_public_id} className="space-y-4">
                <div className="font-semibold text-slate-800 border-b pb-2">
                  {sku.sku_name} ({sku.sku_code}) — {sku.planned_production_qty} Units
                </div>
                <Table headers={['Type', 'Material', 'Gross Required', 'Current ODS Stock', 'Net Request']}>
                  {sku.items.map((item) => (
                    <Tr key={item.material_public_id}>
                      <Td>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${item.material_type === 'RM' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'}`}>
                          {item.material_type}
                        </span>
                      </Td>
                      <Td>{item.material_name} <span className="text-muted-foreground">({item.material_code})</span></Td>
                      <Td className="text-right">{Number(item.gross_required_qty).toFixed(2)}</Td>
                      <Td className="text-right text-orange-600">{Number(item.remaining_from_previous_day).toFixed(2)}</Td>
                      <Td className="text-right text-blue-700 font-bold">{Number(item.requested_qty).toFixed(2)}</Td>
                    </Tr>
                  ))}
                  {sku.items.length === 0 && (
                    <Tr>
                      <Td className="text-center text-muted-foreground py-4">No materials required.</Td>
                    </Tr>
                  )}
                </Table>
              </div>
            ))}
            
            <div className="flex justify-end pt-4 border-t">
              <Button type="button" size="lg" onClick={handleSubmitFinal} isLoading={createMutation.isPending} className="bg-green-600 hover:bg-green-700 text-white">
                Confirm & Submit Request
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
