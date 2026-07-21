import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import { requestsApi } from '@/api/requests'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getErrorMessage } from '@/lib/utils'
import {
  Plus, Trash2, Eye, AlertCircle,
  Loader2, FileSpreadsheet, ArrowLeft, Send, Check
} from 'lucide-react'
import type { RequestPreviewOut } from '@/types/api'
import { Table, Tr, Td } from '@/components/ui/table'

const fadeVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
}

const skuInputSchema = z.object({
  sku_public_id: z.string().min(1, 'Select a SKU'),
  planned_production_qty: z.string().refine(
    (v) => !isNaN(Number(v)) && Number(v) > 0,
    'Must be a positive number',
  ),
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
  const previewRef = useRef<HTMLDivElement>(null)

  const [step, setStep] = useState<'form' | 'preview'>('form')
  const [previewData, setPreviewData] = useState<RequestPreviewOut | null>(null)
  const [submittedValues, setSubmittedValues] = useState<RequestForm | null>(null)

  const { data: skuOptionsData, isLoading: skusLoading, isError: skusError, refetch: refetchSkus } = useQuery({
    queryKey: ['master', 'skuOptions'],
    queryFn: () => masterApi.listSKUOptions(),
    retry: 2,
    staleTime: 30_000,
  })

  const { data: warehousesData } = useQuery({
    queryKey: ['master', 'warehouses'],
    queryFn: () => masterApi.listWarehouses(1, 100),
    retry: 2,
  })

  const odsWarehouses = useMemo(
    () => warehousesData?.data?.filter((w) => w.type === 'ODS') || [],
    [warehousesData],
  )

  const {
    register, control, handleSubmit, watch, setValue,
    formState: { errors },
  } = useForm<RequestForm>({
    resolver: zodResolver(requestSchema as any),
    defaultValues: { request_date: today, notes: '', skus: [], ods_warehouse_public_id: '' },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'skus' })
  const watchWarehouse = watch('ods_warehouse_public_id')

  useEffect(() => {
    if (!watchWarehouse && odsWarehouses.length > 0) {
      setValue('ods_warehouse_public_id', odsWarehouses[0].public_id)
    }
  }, [odsWarehouses, watchWarehouse, setValue])

  const previewMutation = useMutation({
    mutationFn: (data: RequestForm) => requestsApi.previewRequest(data),
    onSuccess: (res, variables) => {
      setPreviewData(res.data)
      setSubmittedValues(variables)
      setStep('preview')
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    onError: (err) => toast.error(getErrorMessage(err)),
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

  const skus = skuOptionsData?.data ?? []
  const skuCount = skus.length
  const noSkusAvailable = !skusLoading && !skusError && skuCount === 0

  const handlePreview = handleSubmit((d) => previewMutation.mutate(d))

  const handleBackToEdit = () => {
    setStep('form')
    setPreviewData(null)
  }

  const handleConfirmSubmit = () => {
    if (!submittedValues) return
    createMutation.mutate(submittedValues)
  }

  const formValues = step === 'preview' ? submittedValues : null
  const selectedWarehouse = odsWarehouses.find(
    (w) => w.public_id === formValues?.ods_warehouse_public_id,
  )

  const steps = [
    { id: 'form', label: 'Build Request' },
    { id: 'preview', label: 'Review & Submit' },
  ]
  const currentStepIndex = steps.findIndex(s => s.id === step)

  return (
    <div className="max-w-6xl mx-auto space-y-8 pb-12" ref={previewRef}>
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">New Production Request</h1>
        <p className="text-muted-foreground mt-1">Plan your daily production and generate material requirements automatically.</p>
      </div>

      {/* Modern Stepper */}
      <div className="relative max-w-2xl mx-auto">
        <div className="absolute left-0 top-1/2 w-full h-0.5 bg-muted -translate-y-1/2 z-0 hidden sm:block"></div>
        <div className="absolute left-0 top-1/2 h-0.5 bg-primary -translate-y-1/2 z-0 hidden sm:block transition-all duration-500" 
             style={{ width: `${(currentStepIndex / (steps.length - 1)) * 100}%` }}></div>
        
        <div className="flex justify-between relative z-10">
          {steps.map((s, i) => {
            const isCompleted = i < currentStepIndex
            const isCurrent = i === currentStepIndex
            return (
              <div key={s.id} className="flex flex-col items-center gap-2 bg-background sm:bg-transparent sm:px-2">
                <div className={`flex h-10 w-10 items-center justify-center rounded-full border-2 font-semibold transition-colors duration-300 ${
                  isCompleted ? 'bg-primary border-primary text-primary-foreground' :
                  isCurrent ? 'bg-background border-primary text-primary shadow-sm' :
                  'bg-background border-muted text-muted-foreground'
                }`}>
                  {isCompleted ? <Check className="h-5 w-5" /> : i + 1}
                </div>
                <span className={`text-sm font-medium ${isCurrent ? 'text-foreground' : 'text-muted-foreground'}`}>
                  {s.label}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      <AnimatePresence mode="wait">
        {step === 'form' && (
          <motion.div key="form" variants={fadeVariants} initial="hidden" animate="visible" exit="exit" className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left: request details */}
            <div className="lg:col-span-1 space-y-6">
              <Card className="rounded-2xl border-none shadow-sm">
                <CardHeader className="pb-4 bg-muted/20 border-b">
                  <CardTitle className="text-lg">Request Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-6">
                  <div className="space-y-2">
                    <Label>Request Date</Label>
                    <Input type="date" {...register('request_date')} className="bg-background shadow-sm" />
                    {errors.request_date && <p className="text-xs text-destructive">{errors.request_date.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label>ODS Warehouse</Label>
                    <Select value={watchWarehouse} onValueChange={(v) => setValue('ods_warehouse_public_id', v)}>
                      <SelectTrigger className="bg-background shadow-sm">
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
                  <div className="space-y-2">
                    <Label>Notes (Optional)</Label>
                    <Input placeholder="E.g. Extra production run" {...register('notes')} className="bg-background shadow-sm" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right: production plan */}
            <div className="lg:col-span-2 space-y-6">
              <Card className="rounded-2xl border-none shadow-sm h-full flex flex-col">
                <CardHeader className="pb-4 border-b bg-muted/20 flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">Production Plan</CardTitle>
                    <CardDescription>Select SKUs and planned quantities</CardDescription>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={noSkusAvailable}
                    onClick={() => append({ sku_public_id: '', planned_production_qty: '' })}
                    className="bg-background shadow-sm rounded-full px-4"
                  >
                    <Plus className="h-4 w-4 mr-1" /> Add SKU
                  </Button>
                </CardHeader>
                <CardContent className="pt-6 space-y-4 flex-1">
                  {/* Empty states */}
                  {fields.length === 0 && (
                    noSkusAvailable ? (
                      <div className="flex flex-col items-center justify-center h-full gap-4 py-12 px-6 text-center border-2 border-dashed border-amber-200 bg-amber-50/50 rounded-xl">
                        <div className="flex items-center justify-center w-12 h-12 rounded-full bg-amber-100 text-amber-600">
                          <FileSpreadsheet className="h-6 w-6" />
                        </div>
                        <div className="space-y-1">
                          <p className="font-semibold text-amber-900">No Finished Goods Available</p>
                          <p className="text-muted-foreground text-sm max-w-xs">
                            Import and commit a Bill of Materials first. SKUs are automatically created from the BOM file.
                          </p>
                        </div>
                        <Button variant="outline" size="sm" className="border-amber-200 text-amber-700 hover:bg-amber-100 mt-2" onClick={() => navigate('/master/bom-upload')}>
                          <FileSpreadsheet className="h-4 w-4 mr-2" /> Go to BOM Upload
                        </Button>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full py-12 text-center border-2 border-dashed rounded-xl bg-muted/10">
                        <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-3">
                          <Plus className="h-6 w-6 text-muted-foreground" />
                        </div>
                        <p className="text-muted-foreground font-medium">Click <strong>Add SKU</strong> to start building the production plan.</p>
                      </div>
                    )
                  )}

                  {/* SKU rows */}
                  <div className="space-y-3">
                    {fields.map((field, index) => (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        key={field.id}
                        className="flex gap-4 items-start p-4 bg-background border shadow-sm rounded-xl"
                      >
                        <div className="flex-1 space-y-2">
                          <Label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Finished Good (SKU)</Label>
                          {skusError ? (
                            <div className="flex items-center gap-2 text-sm text-destructive border border-destructive/30 rounded-md px-3 py-2 bg-destructive/5">
                              <AlertCircle className="h-4 w-4 shrink-0" />
                              <span>Failed to load SKUs.</span>
                              <button type="button" onClick={() => refetchSkus()} className="underline ml-auto text-xs">Retry</button>
                            </div>
                          ) : skusLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground border rounded-md px-3 py-2">
                              <Loader2 className="h-4 w-4 animate-spin" /> Loading SKUs...
                            </div>
                          ) : (
                            <Select value={watch(`skus.${index}.sku_public_id`)} onValueChange={(v) => setValue(`skus.${index}.sku_public_id`, v)}>
                              <SelectTrigger>
                                <SelectValue placeholder={skuCount === 0 ? 'No SKUs found' : 'Select SKU...'} />
                              </SelectTrigger>
                              <SelectContent>
                                {skus.map((s) => (
                                  <SelectItem key={s.public_id} value={s.public_id}>
                                    <span className="font-medium">{s.name}</span> <span className="text-muted-foreground">({s.code})</span>
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                          {errors.skus?.[index]?.sku_public_id && <p className="text-xs text-destructive">{errors.skus[index]?.sku_public_id?.message}</p>}
                        </div>
                        <div className="w-32 space-y-2">
                          <Label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Plan Qty</Label>
                          <Input placeholder="Qty" {...register(`skus.${index}.planned_production_qty`)} />
                          {errors.skus?.[index]?.planned_production_qty && <p className="text-xs text-destructive">{errors.skus[index]?.planned_production_qty?.message}</p>}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="mt-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-full"
                          onClick={() => remove(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </motion.div>
                    ))}
                  </div>

                  {errors.skus?.root && <p className="text-sm text-destructive font-medium p-3 bg-destructive/10 rounded-lg">{errors.skus.root.message}</p>}
                </CardContent>
                <div className="p-4 border-t bg-muted/10 flex justify-between items-center rounded-b-2xl">
                  <Button type="button" variant="ghost" onClick={() => navigate('/ods/requests')} className="rounded-full px-6">
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    onClick={handlePreview}
                    isLoading={previewMutation.isPending}
                    disabled={fields.length === 0}
                    className="rounded-full px-8 shadow-sm"
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    Preview Requirements
                  </Button>
                </div>
              </Card>
            </div>
          </motion.div>
        )}

        {step === 'preview' && (
          <motion.div key="preview" variants={fadeVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
            
            {/* Summary strip */}
            <div className="flex flex-wrap items-center gap-x-8 gap-y-3 bg-white border rounded-2xl p-6 shadow-sm">
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Date</span>
                <span className="font-medium">{formValues?.request_date ? format(new Date(formValues.request_date + 'T00:00:00'), 'dd MMM yyyy') : '—'}</span>
              </div>
              {selectedWarehouse && (
                <div className="flex flex-col border-l pl-8">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Warehouse</span>
                  <span className="font-medium">{selectedWarehouse.name}</span>
                </div>
              )}
              {formValues?.notes && (
                <div className="flex flex-col border-l pl-8 max-w-xs">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Notes</span>
                  <span className="font-medium truncate">{formValues.notes}</span>
                </div>
              )}
              <div className="flex flex-col border-l pl-8">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Total SKUs</span>
                <span className="font-bold text-primary">{previewData?.skus.length ?? 0}</span>
              </div>
            </div>

            {previewData?.no_snapshot_found && (
              <Card className="rounded-2xl border-none shadow-sm bg-blue-50/80">
                <CardContent className="p-6 flex items-start gap-4">
                  <AlertCircle className="h-6 w-6 text-blue-600 shrink-0" />
                  <div>
                    <p className="font-semibold text-blue-900 mb-1">No ODS Inventory Snapshot Found</p>
                    <p className="text-sm text-blue-800">
                      This appears to be the first production request. The system will request the full BOM quantities without deducting existing stock. Ensure you upload today's closing balance after production.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {previewData && (
              <div className="space-y-6">
                {previewData.skus.map((sku) => (
                  <Card key={sku.sku_public_id.toString()} className="rounded-2xl border-none shadow-sm overflow-hidden">
                    <CardHeader className="pb-4 bg-muted/20 border-b flex flex-row items-center justify-between">
                      <div>
                        <CardTitle className="text-lg">{sku.sku_name}</CardTitle>
                        <CardDescription className="font-mono text-xs mt-1">{sku.sku_code}</CardDescription>
                      </div>
                      <div className="bg-primary/10 text-primary px-4 py-1.5 rounded-full font-semibold text-sm">
                        {Number(sku.planned_production_qty).toLocaleString()} units
                      </div>
                    </CardHeader>
                    <div className="overflow-auto">
                      <Table headers={['Type', 'Material', 'Gross Req.', 'ODS Stock', 'Net Request']} className="border-0">
                        {sku.items.map((item) => (
                          <Tr key={item.material_public_id.toString()} className="hover:bg-muted/30">
                            <Td>
                              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                                item.material_type === 'RM' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                              }`}>
                                {item.material_type}
                              </span>
                            </Td>
                            <Td>
                              <div className="font-medium text-sm">{item.material_name}</div>
                              <div className="text-muted-foreground font-mono text-xs mt-1">{item.material_code}</div>
                            </Td>
                            <Td className="text-right text-sm">
                              {Number(item.gross_required_qty).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </Td>
                            <Td className="text-right text-sm font-medium text-orange-600">
                              {Number(item.remaining_from_previous_day).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </Td>
                            <Td className="text-right font-bold text-primary">
                              {Number(item.requested_qty).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </Td>
                          </Tr>
                        ))}
                        {sku.items.length === 0 && (
                          <Tr>
                            <Td className="text-center text-muted-foreground py-8 col-span-5 border-0">
                              No materials required for this SKU.
                            </Td>
                          </Tr>
                        )}
                      </Table>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* Legend */}
            <div className="flex flex-wrap gap-6 text-sm text-muted-foreground bg-muted/20 px-6 py-4 rounded-xl border">
              <span className="flex items-center gap-2">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-slate-400" />
                <strong>Gross Req.</strong> = BOM qty × planned units
              </span>
              <span className="flex items-center gap-2">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-orange-400" />
                <strong>ODS Stock</strong> = current inventory in warehouse
              </span>
              <span className="flex items-center gap-2">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-primary" />
                <strong>Net Request</strong> = max(Gross − ODS Stock, 0)
              </span>
            </div>

            {/* Action bar */}
            <div className="flex justify-between items-center pt-4 border-t">
              <Button type="button" variant="outline" onClick={handleBackToEdit} disabled={createMutation.isPending} className="rounded-full px-6">
                <ArrowLeft className="h-4 w-4 mr-2" /> Back to Edit
              </Button>
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted-foreground hidden sm:block bg-amber-50 px-4 py-1.5 rounded-full text-amber-700 font-medium">
                  Request will be marked as Pending Approval
                </span>
                <Button
                  type="button"
                  size="lg"
                  onClick={handleConfirmSubmit}
                  isLoading={createMutation.isPending}
                  className="rounded-full px-8 shadow-sm bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <Send className="h-4 w-4 mr-2" /> Submit Request
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
