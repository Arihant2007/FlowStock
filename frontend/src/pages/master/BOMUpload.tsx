import { useState, useEffect, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Table, Tr, Td } from '@/components/ui/table'
import { getErrorMessage } from '@/lib/utils'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { Upload, CheckCircle2, XCircle, AlertCircle, FileSpreadsheet, Download, ChevronRight, Check } from 'lucide-react'
import type { BOMUploadPreview } from '@/types/api'

const fadeVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
}

export function BOMUploadPage() {
  const [_file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<BOMUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'pending_session' | 'preview' | 'done'>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [commitResult, setCommitResult] = useState<any>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const savedSession = sessionStorage.getItem('bomUploadSessionId')
    if (savedSession) {
      setSessionId(savedSession)
      setStep('pending_session')
    }
  }, [])

  const previewMutation = useMutation({
    mutationFn: (params: { file?: File; sessionId?: string }) => masterApi.previewBOMUpload(params),
    onSuccess: (data) => {
      setPreview(data.data)
      if (data.data.session_id) {
        sessionStorage.setItem('bomUploadSessionId', data.data.session_id)
        setSessionId(data.data.session_id)
      }
      setStep('preview')
    },
    onError: (err) => {
      toast.error(getErrorMessage(err))
      if (err.message?.includes('expired') || err.message?.includes('found')) {
        sessionStorage.removeItem('bomUploadSessionId')
        setSessionId(null)
        setStep('upload')
      }
    },
  })

  const qc = useQueryClient()

  const commitMutation = useMutation({
    mutationFn: (sId: string) => masterApi.commitBOMUpload(sId),
    onSuccess: (data) => {
      toast.success('BOM imported successfully.')
      qc.invalidateQueries({ queryKey: ['master', 'skus'] })
      qc.invalidateQueries({ queryKey: ['master', 'skuOptions'] })
      qc.invalidateQueries({ queryKey: ['master', 'dashboard', 'stats'] })
      sessionStorage.removeItem('bomUploadSessionId')
      setSessionId(null)
      setCommitResult(data.data)
      setStep('done')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const cancelMutation = useMutation({
    mutationFn: (sId: string) => masterApi.cancelBOMUpload(sId),
    onSuccess: () => {
      sessionStorage.removeItem('bomUploadSessionId')
      setSessionId(null)
      setFile(null)
      setPreview(null)
      setStep('upload')
      toast.success('Upload session cancelled')
    },
  })

  const processFile = (f: File) => {
    setFile(f)
    setPreview(null)
    previewMutation.mutate({ file: f })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) processFile(f)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
      processFile(f)
    } else {
      toast.error('Please upload a valid Excel file (.xlsx or .xls)')
    }
  }

  const handleReplace = () => {
    if (sessionId) {
      cancelMutation.mutate(sessionId)
    } else {
      setFile(null)
      setPreview(null)
      setStep('upload')
    }
  }

  const steps = [
    { id: 'upload', label: '1. Upload File' },
    { id: 'preview', label: '2. Review & Validate' },
    { id: 'done', label: '3. Import Complete' },
  ]
  const currentStepIndex = step === 'pending_session' ? 0 : steps.findIndex((s) => s.id === step)

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <PageHeader
        title="BOM Upload Wizard"
        subtitle="Import multi-level Bills of Materials to associate finished goods SKUs with raw materials"
      />

      {/* Stepper Progress Bar */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between max-w-xl mx-auto">
          {steps.map((s, i) => {
            const isCompleted = i < currentStepIndex
            const isCurrent = i === currentStepIndex

            return (
              <div key={s.id} className="flex items-center gap-2.5">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-all ${
                    isCompleted
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : isCurrent
                      ? 'bg-blue-600 text-white ring-4 ring-blue-100 shadow-sm'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isCompleted ? <Check className="h-4 w-4" /> : i + 1}
                </div>
                <span className={`text-xs font-semibold ${isCurrent ? 'text-slate-900' : 'text-slate-400'}`}>
                  {s.label}
                </span>
                {i < steps.length - 1 && <div className="h-0.5 w-12 bg-slate-100 mx-2 hidden sm:block" />}
              </div>
            )
          })}
        </div>
      </div>

      <AnimatePresence mode="wait">
        {step === 'pending_session' && (
          <motion.div key="pending" variants={fadeVariants} initial="hidden" animate="visible" exit="exit">
            <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-6 space-y-4 shadow-sm">
              <div>
                <h3 className="font-bold text-amber-950 text-base">Unfinished BOM Session Detected</h3>
                <p className="text-xs text-amber-900 mt-0.5">
                  You have a previously uploaded BOM session in progress. You can resume or discard it.
                </p>
              </div>
              <div className="flex gap-3">
                <Button
                  onClick={() => previewMutation.mutate({ sessionId: sessionId! })}
                  disabled={previewMutation.isPending}
                  className="rounded-xl bg-amber-600 hover:bg-amber-700 text-white h-9 px-5 text-xs font-semibold shadow-sm"
                >
                  Resume Session
                </Button>
                <Button
                  variant="outline"
                  onClick={handleReplace}
                  disabled={cancelMutation.isPending}
                  className="rounded-xl border-amber-200 text-amber-900 hover:bg-amber-100 h-9 px-4 text-xs font-semibold"
                >
                  Discard & Start New
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        {step === 'upload' && (
          <motion.div key="upload" variants={fadeVariants} initial="hidden" animate="visible" exit="exit">
            <div className="rounded-2xl border border-slate-200/80 bg-white p-8 shadow-sm">
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative flex flex-col items-center justify-center w-full min-h-[320px] border-2 border-dashed rounded-2xl cursor-pointer transition-all ${
                  isDragging
                    ? 'border-blue-600 bg-blue-50/50 scale-[1.005]'
                    : 'border-slate-200 bg-slate-50/40 hover:border-blue-400 hover:bg-slate-50'
                }`}
              >
                <input ref={fileInputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />

                {previewMutation.isPending ? (
                  <div className="flex flex-col items-center text-blue-600">
                    <div className="h-10 w-10 rounded-full border-4 border-blue-200 border-t-blue-600 animate-spin mb-3" />
                    <p className="font-semibold text-xs text-slate-700">Analyzing BOM File Structure...</p>
                  </div>
                ) : (
                  <>
                    <div className="h-14 w-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-3 text-blue-600 shadow-sm border border-blue-100">
                      <Upload className="h-7 w-7" />
                    </div>
                    <h3 className="text-base font-bold text-slate-900 mb-1">Drag & drop your BOM Excel file here</h3>
                    <p className="text-xs text-slate-500 mb-4">or click to browse from your device</p>
                    <div className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-xs">
                      <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" /> Excel Format (.xlsx, .xls)
                    </div>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {step === 'preview' && preview && (
          <motion.div key="preview" variants={fadeVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title="Valid Rows"
                value={preview.valid_rows}
                subtext="Valid Recipes"
                icon={CheckCircle2}
                badge={{ text: 'Valid', variant: 'success' }}
              />
              <MetricCard
                title="Error Rows"
                value={preview.error_rows}
                subtext="Action Required"
                icon={XCircle}
                badge={{ text: preview.error_rows > 0 ? 'Error' : 'Clean', variant: preview.error_rows > 0 ? 'danger' : 'success' }}
              />
              <MetricCard
                title="Pending Materials"
                value={Array.isArray(preview.pending_rows) ? preview.pending_rows.length : (preview.pending_rows ?? 0)}
                subtext="Missing Material Master"
                icon={AlertCircle}
                badge={{ text: 'Pending', variant: 'warning' }}
              />
              <MetricCard
                title="Total BOM Rows"
                value={preview.total_rows}
                subtext="Processed Data"
                icon={FileSpreadsheet}
              />
            </div>

            {/* SadaxCart Data Table Container */}
            <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden space-y-2">
              <div className="p-4 border-b border-slate-100">
                <h3 className="font-bold text-slate-900 text-sm">BOM Structure Preview</h3>
                <p className="text-xs text-slate-500">Review SKU code, material quantities, and status</p>
              </div>

              <Table
                headers={['Row', 'SKU Code', 'Material Code', 'Qty per Unit', 'Status', 'Message']}
                isEmpty={preview.rows.length === 0}
                className="border-0 shadow-none rounded-none"
              >
                {preview.rows.map((row) => (
                  <Tr key={row.row_number}>
                    <Td className="text-slate-400 font-mono text-xs text-center">{row.row_number}</Td>
                    <Td className="font-mono text-xs font-semibold text-slate-900">{row.sku_code}</Td>
                    <Td className="font-mono text-xs font-semibold text-blue-700">{row.material_code}</Td>
                    <Td className="font-semibold text-slate-900 text-xs">{row.quantity_per_unit}</Td>
                    <Td>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                          row.status === 'valid'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : row.status === 'error'
                            ? 'bg-red-50 text-red-700 border-red-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}
                      >
                        {row.status.toUpperCase()}
                      </span>
                    </Td>
                    <Td className="text-slate-500 text-xs max-w-[200px] truncate">{row.message || '—'}</Td>
                  </Tr>
                ))}
              </Table>
            </div>

            {/* Missing Materials Extraction Banner */}
            {preview.unknown_materials && preview.unknown_materials.length > 0 && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h4 className="font-bold text-amber-950 text-sm flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-amber-600" /> {preview.unknown_materials.length} Missing Materials Found
                  </h4>
                  <p className="text-xs text-amber-900 mt-1">
                    Download the auto-generated template, upload missing materials to Material Master, then click "Resume BOM Import".
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={async () => {
                    try {
                      const blob = await masterApi.extractMaterialsFromBOM(null, sessionId, true)
                      const url = window.URL.createObjectURL(new Blob([blob]))
                      const link = document.createElement('a')
                      link.href = url
                      link.setAttribute('download', 'extracted_materials.xlsx')
                      document.body.appendChild(link)
                      link.click()
                      link.remove()
                      toast.success('Downloaded extracted materials template.')
                    } catch (e: any) {
                      toast.error(`Extraction failed: ${getErrorMessage(e)}`)
                    }
                  }}
                  className="rounded-xl border-amber-300 text-amber-950 hover:bg-amber-100 h-9 px-4 text-xs font-semibold shrink-0"
                >
                  <Download className="mr-1.5 h-3.5 w-3.5" /> Download Materials Template
                </Button>
              </div>
            )}

            {/* Action Bar */}
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                onClick={handleReplace}
                className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 h-10 px-5 text-xs font-semibold"
              >
                Cancel Session
              </Button>
              <Button
                onClick={() => {
                  if (preview.session_status === 'WAITING_FOR_MATERIALS') {
                    if (sessionId) previewMutation.mutate({ sessionId })
                  } else {
                    if (sessionId) commitMutation.mutate(sessionId)
                  }
                }}
                disabled={preview.session_status !== 'READY_TO_COMMIT' && preview.session_status !== 'WAITING_FOR_MATERIALS'}
                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-10 px-6 text-xs font-semibold shadow-sm"
              >
                {preview.session_status === 'WAITING_FOR_MATERIALS' ? 'Resume BOM Import' : 'Commit BOM to Database'}
                {preview.session_status !== 'WAITING_FOR_MATERIALS' && <ChevronRight className="ml-1.5 h-4 w-4" />}
              </Button>
            </div>
          </motion.div>
        )}

        {step === 'done' && commitResult && (
          <motion.div key="done" variants={fadeVariants} initial="hidden" animate="visible" exit="exit">
            <div className="rounded-2xl border border-slate-200/80 bg-white p-12 text-center shadow-sm max-w-lg mx-auto flex flex-col items-center">
              <div className="h-16 w-16 bg-emerald-50 rounded-full flex items-center justify-center mb-4 border border-emerald-100">
                <CheckCircle2 className="h-8 w-8 text-emerald-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-1">BOM Import Completed</h3>
              <p className="text-xs text-slate-500 mb-6">
                Created {commitResult.skus_created} SKUs, updated {commitResult.skus_updated} SKUs, and registered {commitResult.items_created} BOM items.
              </p>
              <Button
                onClick={() => {
                  setStep('upload')
                  setFile(null)
                  setPreview(null)
                  setCommitResult(null)
                }}
                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white px-6 h-10 text-xs font-semibold shadow-sm"
              >
                Upload Another BOM File
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
