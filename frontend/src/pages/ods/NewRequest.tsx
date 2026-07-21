import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
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
import {
  ClipboardList, Plus, Trash2, Eye, CheckCircle, AlertCircle,
  Loader2, FileSpreadsheet, ArrowLeft, Send, Pencil,
} from 'lucide-react'
import type { RequestPreviewOut } from '@/types/api'
import { Table, Tr, Td } from '@/components/ui/table'

// ─── Zod schemas ──────────────────────────────────────────────────────────────

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

// ─── Step indicator ───────────────────────────────────────────────────────────

function StepIndicator({ step }: { step: 1 | 2 }) {
  return (
    <div className="flex items-center gap-2 text-sm select-none">
      <div className={`flex items-center gap-1.5 ${step === 1 ? 'text-primary font-semibold' : 'text-muted-foreground'}`}>
        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors
          ${step === 1 ? 'border-primary bg-primary text-white' : 'border-green-500 bg-green-500 text-white'}`}>
          {step > 1 ? <CheckCircle className="h-3.5 w-3.5" /> : '1'}
        </div>
        Build Request
      </div>
      <div className={`h-px w-8 transition-colors ${step === 2 ? 'bg-primary' : 'bg-border'}`} />
      <div className={`flex items-center gap-1.5 ${step === 2 ? 'text-primary font-semibold' : 'text-muted-foreground'}`}>
        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors
          ${step === 2 ? 'border-primary bg-primary text-white' : 'border-border bg-background'}`}>
          2
        </div>
        Review & Submit
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function NewRequestPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const today = format(new Date(), 'yyyy-MM-dd')
  const previewRef = useRef<HTMLDivElement>(null)

  // Two-step state: 'form' | 'preview'
  const [step, setStep] = useState<'form' | 'preview'>('form')
  const [previewData, setPreviewData] = useState<RequestPreviewOut | null>(null)
  // Cache the submitted form values so the preview Submit can replay them without re-validating
  const [submittedValues, setSubmittedValues] = useState<RequestForm | null>(null)

  // ── Data queries ──────────────────────────────────────────────────────────

  const {
    data: skuOptionsData,
    isLoading: skusLoading,
    isError: skusError,
    refetch: refetchSkus,
  } = useQuery({
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

  // ── Form ──────────────────────────────────────────────────────────────────

  const {
    register, control, handleSubmit, watch, setValue,
    formState: { errors },
    getValues,
  } = useForm<RequestForm>({
    resolver: zodResolver(requestSchema as any),
    defaultValues: { request_date: today, notes: '', skus: [], ods_warehouse_public_id: '' },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'skus' })
  const watchWarehouse = watch('ods_warehouse_public_id')

  // Auto-select first ODS warehouse
  useEffect(() => {
    if (!watchWarehouse && odsWarehouses.length > 0) {
      setValue('ods_warehouse_public_id', odsWarehouses[0].public_id)
    }
  }, [odsWarehouses, watchWarehouse, setValue])

  // ── Mutations ─────────────────────────────────────────────────────────────

  const previewMutation = useMutation({
    mutationFn: (data: RequestForm) => requestsApi.previewRequest(data),
    onSuccess: (res, variables) => {
      setPreviewData(res.data)
      setSubmittedValues(variables)
      setStep('preview')
      // Scroll to top so the preview header is visible
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const createMutation = useMutation({
    mutationFn: (data: RequestForm) => requestsApi.createRequest(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['requests'] })
      toast.success('Morning request submitted — pending approval.')
      navigate('/ods/requests')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  // ── Derived values ────────────────────────────────────────────────────────

  const skus = skuOptionsData?.data ?? []
  const skuCount = skus.length
  const noSkusAvailable = !skusLoading && !skusError && skuCount === 0

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handlePreview = handleSubmit((d) => previewMutation.mutate(d))

  const handleBackToEdit = () => {
    setStep('form')
    setPreviewData(null)
  }

  const handleConfirmSubmit = () => {
    if (!submittedValues) return
    createMutation.mutate(submittedValues)
  }

  // ── Summary line for preview header ──────────────────────────────────────

  const formValues = step === 'preview' ? submittedValues : null
  const selectedWarehouse = odsWarehouses.find(
    (w) => w.public_id === formValues?.ods_warehouse_public_id,
  )

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER — STEP 1: FORM
  // ─────────────────────────────────────────────────────────────────────────

  if (step === 'form') {
    return (
      <div className="space-y-6 animate-fade-in max-w-5xl mx-auto pb-12">
        {/* Page header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <ClipboardList className="h-6 w-6" /> New Morning Request
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              Fill the production plan, then preview material requirements before submitting.
            </p>
          </div>
          <StepIndicator step={1} />
        </div>

        {/* Body grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: request details */}
          <div className="lg:col-span-1 space-y-6">
            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-base">Request Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <Label>Request Date</Label>
                  <Input type="date" {...register('request_date')} />
                  {errors.request_date && (
                    <p className="text-xs text-destructive">{errors.request_date.message}</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label>ODS Warehouse</Label>
                  <Select
                    value={watchWarehouse}
                    onValueChange={(v) => setValue('ods_warehouse_public_id', v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select ODS Warehouse" />
                    </SelectTrigger>
                    <SelectContent>
                      {odsWarehouses.map((w) => (
                        <SelectItem key={w.public_id} value={w.public_id}>
                          {w.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {errors.ods_warehouse_public_id && (
                    <p className="text-xs text-destructive">
                      {errors.ods_warehouse_public_id.message}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label>Notes (Optional)</Label>
                  <Input placeholder="E.g. Extra production run" {...register('notes')} />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right: production plan */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader className="pb-4 flex flex-row items-center justify-between border-b">
                <div>
                  <CardTitle className="text-base">Production Plan</CardTitle>
                  {!skusLoading && !skusError && skuCount > 0 && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {skuCount} SKU{skuCount !== 1 ? 's' : ''} available
                    </p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={noSkusAvailable}
                  onClick={() => append({ sku_public_id: '', planned_production_qty: '' })}
                >
                  <Plus className="h-4 w-4 mr-1" /> Add SKU
                </Button>
              </CardHeader>
              <CardContent className="pt-4 space-y-4">
                {/* Empty states */}
                {fields.length === 0 && (
                  noSkusAvailable ? (
                    <div className="flex flex-col items-center gap-4 py-10 px-6 text-center border-2 border-dashed border-amber-300 bg-amber-50/60 rounded-lg">
                      <div className="flex items-center justify-center w-12 h-12 rounded-full bg-amber-100 text-amber-600">
                        <FileSpreadsheet className="h-6 w-6" />
                      </div>
                      <div className="space-y-1">
                        <p className="font-semibold text-slate-800 text-sm">
                          No Finished Goods (SKUs) available
                        </p>
                        <p className="text-muted-foreground text-xs max-w-xs">
                          Import and commit a Bill of Materials first. SKUs are automatically
                          created from the BOM file.
                        </p>
                      </div>
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="border-amber-400 text-amber-700 hover:bg-amber-100"
                      >
                        <Link to="/master/bom-upload">
                          <FileSpreadsheet className="h-4 w-4 mr-2" />
                          Go to BOM Upload
                        </Link>
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                      Click <strong>Add SKU</strong> to start building the production plan.
                    </div>
                  )
                )}

                {/* SKU rows */}
                {fields.map((field, index) => (
                  <div
                    key={field.id}
                    className="flex gap-4 items-start p-4 bg-slate-50 border rounded-lg"
                  >
                    <div className="flex-1 space-y-1.5">
                      <Label>Finished Good (SKU)</Label>
                      {skusError ? (
                        <div className="flex items-center gap-2 text-sm text-destructive border border-destructive/30 rounded-md px-3 py-2 bg-destructive/5">
                          <AlertCircle className="h-4 w-4 shrink-0" />
                          <span>Failed to load SKUs.</span>
                          <button
                            type="button"
                            onClick={() => refetchSkus()}
                            className="underline ml-auto text-xs"
                          >
                            Retry
                          </button>
                        </div>
                      ) : skusLoading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground border rounded-md px-3 py-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Loading SKUs…
                        </div>
                      ) : (
                        <Select
                          value={watch(`skus.${index}.sku_public_id`)}
                          onValueChange={(v) => setValue(`skus.${index}.sku_public_id`, v)}
                        >
                          <SelectTrigger>
                            <SelectValue
                              placeholder={
                                skuCount === 0
                                  ? 'No SKUs found — import a BOM first'
                                  : 'Select SKU…'
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {skus.map((s) => (
                              <SelectItem key={s.public_id} value={s.public_id}>
                                {s.name} ({s.code})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      {errors.skus?.[index]?.sku_public_id && (
                        <p className="text-xs text-destructive">
                          {errors.skus[index]?.sku_public_id?.message}
                        </p>
                      )}
                    </div>
                    <div className="w-32 space-y-1.5">
                      <Label>Plan Qty</Label>
                      <Input
                        placeholder="Qty"
                        {...register(`skus.${index}.planned_production_qty`)}
                      />
                      {errors.skus?.[index]?.planned_production_qty && (
                        <p className="text-xs text-destructive">
                          {errors.skus[index]?.planned_production_qty?.message}
                        </p>
                      )}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="mt-6 text-destructive hover:bg-destructive/10"
                      onClick={() => remove(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}

                {errors.skus?.root && (
                  <p className="text-sm text-destructive">{errors.skus.root.message}</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Action bar */}
        <div className="flex justify-between items-center pt-2 border-t">
          <Button type="button" variant="ghost" onClick={() => navigate('/ods/requests')}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handlePreview}
            isLoading={previewMutation.isPending}
            disabled={fields.length === 0}
          >
            <Eye className="h-4 w-4 mr-2" />
            Preview Material Requirements
          </Button>
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER — STEP 2: PREVIEW & SUBMIT
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl mx-auto pb-12" ref={previewRef}>
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ClipboardList className="h-6 w-6" /> Review Request
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Verify the calculated material requirements, then submit for RMPM approval.
          </p>
        </div>
        <StepIndicator step={2} />
      </div>

      {/* Summary strip */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground bg-slate-50 border rounded-lg px-4 py-3">
        <span>
          <strong className="text-slate-700">Date:</strong>{' '}
          {formValues?.request_date
            ? format(new Date(formValues.request_date + 'T00:00:00'), 'dd MMM yyyy')
            : '—'}
        </span>
        {selectedWarehouse && (
          <span>
            <strong className="text-slate-700">Warehouse:</strong> {selectedWarehouse.name}
          </span>
        )}
        {formValues?.notes && (
          <span>
            <strong className="text-slate-700">Notes:</strong> {formValues.notes}
          </span>
        )}
        <span>
          <strong className="text-slate-700">SKUs:</strong>{' '}
          {previewData?.skus.length ?? 0}
        </span>
      </div>

      {/* Material requirements table per SKU */}
      {previewData?.no_snapshot_found && (
        <div className="bg-blue-50 border border-blue-200 text-blue-800 rounded-lg p-4 flex gap-3 text-sm">
          <AlertCircle className="h-5 w-5 shrink-0 text-blue-600" />
          <p>
            No previous ODS inventory snapshot found. This appears to be the first production request. The system will request the full BOM quantities. Upload today's remaining inventory after production so future requests can deduct available stock.
          </p>
        </div>
      )}

      {previewData && (
        <div className="space-y-6">
          {previewData.skus.map((sku) => (
            <Card key={sku.sku_public_id.toString()} className="border-slate-200">
              <CardHeader className="pb-3 border-b bg-slate-50/60 rounded-t-lg">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold">
                    {sku.sku_name}{' '}
                    <span className="font-normal text-muted-foreground text-sm">
                      ({sku.sku_code})
                    </span>
                  </CardTitle>
                  <span className="text-sm font-medium bg-primary/10 text-primary px-2.5 py-0.5 rounded-full">
                    {Number(sku.planned_production_qty).toLocaleString()} units planned
                  </span>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <Table headers={['Type', 'Material', 'Gross Req.', 'ODS Stock', 'Net Request']}>
                  {sku.items.map((item) => (
                    <Tr key={item.material_public_id.toString()}>
                      <Td>
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-semibold ${
                            item.material_type === 'RM'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-purple-100 text-purple-800'
                          }`}
                        >
                          {item.material_type}
                        </span>
                      </Td>
                      <Td>
                        {item.material_name}{' '}
                        <span className="text-muted-foreground text-xs">
                          ({item.material_code})
                        </span>
                      </Td>
                      <Td className="text-right tabular-nums">
                        {Number(item.gross_required_qty).toFixed(2)}
                      </Td>
                      <Td className="text-right tabular-nums text-orange-600">
                        {Number(item.remaining_from_previous_day).toFixed(2)}
                      </Td>
                      <Td className="text-right tabular-nums text-blue-700 font-bold">
                        {Number(item.requested_qty).toFixed(2)}
                      </Td>
                    </Tr>
                  ))}
                  {sku.items.length === 0 && (
                    <Tr>
                      <Td className="text-center text-muted-foreground py-4 col-span-5">
                        No materials required for this SKU.
                      </Td>
                    </Tr>
                  )}
                </Table>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-slate-400" />
          Gross Req. = BOM qty × planned units
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-orange-400" />
          ODS Stock = current inventory in the ODS warehouse
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
          Net Request = max(Gross − ODS Stock, 0)
        </span>
      </div>

      {/* Action bar */}
      <div className="flex justify-between items-center pt-4 border-t">
        <Button
          type="button"
          variant="outline"
          onClick={handleBackToEdit}
          disabled={createMutation.isPending}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back &amp; Edit
        </Button>

        <div className="flex items-center gap-3">
          <p className="text-xs text-muted-foreground hidden sm:block">
            Request will be saved with <strong>Pending Approval</strong> status.
          </p>
          <Button
            type="button"
            size="lg"
            onClick={handleConfirmSubmit}
            isLoading={createMutation.isPending}
            className="bg-green-600 hover:bg-green-700 text-white min-w-40"
          >
            <Send className="h-4 w-4 mr-2" />
            Submit Request
          </Button>
        </div>
      </div>
    </div>
  )
}
