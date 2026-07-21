import { useState, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Table, Tr, Td } from '@/components/ui/table'
import { getErrorMessage } from '@/lib/utils'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { Upload, CheckCircle2, XCircle, AlertCircle, FileSpreadsheet, Download, ChevronRight, Check } from 'lucide-react'
import type { MaterialUploadPreview } from '@/types/api'

const fadeVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
}

export function MaterialUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<MaterialUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload')
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const previewMutation = useMutation({
    mutationFn: (f: File) => masterApi.previewMaterialUpload(f),
    onSuccess: (data) => {
      setPreview(data.data)
      setStep('preview')
    },
    onError: (err) => {
      toast.error(getErrorMessage(err))
      setFile(null)
    },
  })

  const commitMutation = useMutation({
    mutationFn: (f: File) => masterApi.commitMaterialUpload(f),
    onSuccess: (data) => {
      const { created, updated, skipped } = data.data as any
      toast.success(`Material Master uploaded! Created: ${created}, Updated: ${updated}, Skipped: ${skipped}.`)
      setStep('done')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const handleDownloadTemplate = async () => {
    try {
      const blob = await masterApi.downloadMaterialTemplate()
      const url = window.URL.createObjectURL(new Blob([blob]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'material_master_template.xlsx')
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch {
      toast.error('Failed to download template')
    }
  }

  const processFile = (f: File) => {
    setFile(f)
    setPreview(null)
    previewMutation.mutate(f)
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

  const handleGenerateFromBOM = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    try {
      toast.info('Generating template from BOM...')
      const blob = await masterApi.extractMaterialsFromBOM(f, null, true)
      const url = window.URL.createObjectURL(new Blob([blob]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'extracted_materials.xlsx')
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Generated template downloaded. Fill it and upload here.')
    } catch (err: any) {
      console.error('Failed to generate template from BOM', err)
      toast.error(`Failed to generate template from BOM: ${getErrorMessage(err) || err.message}`)
    } finally {
      e.target.value = ''
    }
  }

  const steps = [
    { id: 'upload', label: '1. Select File' },
    { id: 'preview', label: '2. Validate & Review' },
    { id: 'done', label: '3. Commit Master' },
  ]
  const currentStepIndex = steps.findIndex((s) => s.id === step)

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <PageHeader
        title="Material Master Upload Wizard"
        subtitle="Batch import new Raw Materials (RM) and Packaging Materials (PM) via Excel template"
      >
        <Button
          variant="outline"
          onClick={() => document.getElementById('bom-gen-input')?.click()}
          className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 h-9 text-xs font-semibold"
        >
          <FileSpreadsheet className="mr-1.5 h-3.5 w-3.5 text-slate-500" /> Extract from BOM
        </Button>
        <input id="bom-gen-input" type="file" accept=".xlsx,.xls" className="hidden" onChange={handleGenerateFromBOM} />

        <Button
          variant="outline"
          onClick={handleDownloadTemplate}
          className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 h-9 text-xs font-semibold"
        >
          <Download className="mr-1.5 h-3.5 w-3.5 text-slate-500" /> Download Template
        </Button>
      </PageHeader>

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

      {/* Wizard Content */}
      <AnimatePresence mode="wait">
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
                    <p className="font-semibold text-xs text-slate-700">Analyzing Material Master File...</p>
                  </div>
                ) : (
                  <>
                    <div className="h-14 w-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-3 text-blue-600 shadow-sm border border-blue-100">
                      <Upload className="h-7 w-7" />
                    </div>
                    <h3 className="text-base font-bold text-slate-900 mb-1">Drag & drop your Excel file here</h3>
                    <p className="text-xs text-slate-500 mb-4">or click to browse from your device</p>
                    <div className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-xs">
                      <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" /> Excel Spreadsheet (.xlsx, .xls)
                    </div>
                  </>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {step === 'preview' && preview && (
          <motion.div key="preview" variants={fadeVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title="Valid Rows"
                value={preview.valid_rows}
                subtext="Ready to Import"
                icon={CheckCircle2}
                badge={{ text: 'Valid', variant: 'success' }}
              />
              <MetricCard
                title="Skipped Rows"
                value={preview.skipped_rows_count}
                subtext="No Material Changes"
                icon={AlertCircle}
                badge={{ text: 'Unchanged', variant: 'warning' }}
              />
              <MetricCard
                title="Error Rows"
                value={preview.error_rows}
                subtext="Require Correction"
                icon={XCircle}
                badge={{ text: preview.error_rows > 0 ? 'Critical Error' : 'Clean', variant: preview.error_rows > 0 ? 'danger' : 'success' }}
              />
              <MetricCard
                title="Total Rows"
                value={preview.total_rows}
                subtext={`New: ${preview.new_materials.length} · Updated: ${preview.updated_materials.length}`}
                icon={FileSpreadsheet}
              />
            </div>

            {/* Errors / Warnings */}
            {(preview.errors.length > 0 || (preview.warnings && preview.warnings.length > 0)) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {preview.errors.length > 0 && (
                  <div className="rounded-2xl border border-red-200 bg-red-50/60 p-4 space-y-2">
                    <h4 className="font-bold text-red-900 text-xs flex items-center gap-1.5">
                      <AlertCircle className="h-4 w-4 text-red-600" /> Global Validation Errors
                    </h4>
                    <ul className="text-xs text-red-700 space-y-1 list-disc pl-4 font-medium">
                      {preview.errors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {preview.warnings && preview.warnings.length > 0 && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 space-y-2">
                    <h4 className="font-bold text-amber-900 text-xs flex items-center gap-1.5">
                      <AlertCircle className="h-4 w-4 text-amber-600" /> Validation Warnings
                    </h4>
                    <ul className="text-xs text-amber-800 space-y-1 list-disc pl-4 font-medium">
                      {preview.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* SadaxCart Table Container */}
            <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden space-y-2">
              <div className="p-4 border-b border-slate-100">
                <h3 className="font-bold text-slate-900 text-sm">Parsed File Rows Preview</h3>
                <p className="text-xs text-slate-500">Review status of each row before committing to the system</p>
              </div>

              <Table
                headers={['Row', 'Material Code', 'Description', 'UoM', 'Category', 'Type', 'Status', 'Validation Message']}
                isEmpty={preview.rows.length === 0}
                className="border-0 shadow-none rounded-none"
              >
                {preview.rows.map((row) => (
                  <Tr key={row.row_number}>
                    <Td className="text-slate-400 font-mono text-xs text-center">{row.row_number}</Td>
                    <Td className="font-mono text-xs font-semibold text-slate-900">{row.material_code}</Td>
                    <Td className="font-medium text-slate-900 text-xs">{row.material_name}</Td>
                    <Td className="font-mono text-xs text-slate-600">{row.uom}</Td>
                    <Td className="text-slate-600 text-xs">{row.category}</Td>
                    <Td className="text-slate-600 text-xs">{row.material_type}</Td>
                    <Td>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                          row.status === 'valid'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : row.status === 'skipped'
                            ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-red-50 text-red-700 border-red-200'
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

            {/* Action Bar */}
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                onClick={() => setStep('upload')}
                className="rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-50 h-10 px-5 text-xs font-semibold"
              >
                Back to Selection
              </Button>
              <Button
                onClick={() => file && commitMutation.mutate(file)}
                disabled={preview.error_rows > 0 || commitMutation.isPending}
                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-10 px-6 text-xs font-semibold shadow-sm"
              >
                {preview.error_rows > 0 ? 'Resolve Errors to Commit' : 'Commit Master Records'}
                {!preview.error_rows && <ChevronRight className="ml-1.5 h-4 w-4" />}
              </Button>
            </div>
          </motion.div>
        )}

        {step === 'done' && (
          <motion.div key="done" variants={fadeVariants} initial="hidden" animate="visible" exit="exit">
            <div className="rounded-2xl border border-slate-200/80 bg-white p-12 text-center shadow-sm max-w-lg mx-auto flex flex-col items-center">
              <div className="h-16 w-16 bg-emerald-50 rounded-full flex items-center justify-center mb-4 border border-emerald-100">
                <CheckCircle2 className="h-8 w-8 text-emerald-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-1">Upload Completed Successfully</h3>
              <p className="text-xs text-slate-500 mb-6">
                Your Material Master records have been safely validated and written to the database.
              </p>
              <Button
                onClick={() => {
                  setStep('upload')
                  setFile(null)
                  setPreview(null)
                }}
                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white px-6 h-10 text-xs font-semibold shadow-sm"
              >
                Upload Another Master File
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
