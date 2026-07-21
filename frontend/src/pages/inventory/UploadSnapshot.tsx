import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'
import { inventoryApi } from '@/api/inventory'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { getErrorMessage } from '@/lib/utils'
import { Upload, CheckCircle2, AlertCircle, FileSpreadsheet, ChevronRight, Check } from 'lucide-react'
import type { OpeningBalanceUploadPreview } from '@/types/api'

const fadeVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
}

export function InventoryUploadPage() {
  const qc = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<OpeningBalanceUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload')
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const previewMutation = useMutation({
    mutationFn: (f: File) => inventoryApi.previewUpload(f),
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
    mutationFn: (f: File) => inventoryApi.commitUpload(f, true),
    onSuccess: (data) => {
      const res = data.data as any
      toast.success(`Inventory updated! ${res.adjustments_created} adjustment(s) created.`)
      qc.invalidateQueries({ queryKey: ['inventory'] })
      setStep('done')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

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

  const steps = [
    { id: 'upload', label: 'Upload Snapshot' },
    { id: 'preview', label: 'Preview Reconciliations' },
    { id: 'done', label: 'Complete' },
  ]
  const currentStepIndex = steps.findIndex(s => s.id === step)

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Inventory Snapshot Upload</h1>
        <p className="text-muted-foreground mt-1">Upload daily closing balances to reconcile the system ledger.</p>
      </div>

      {/* Modern Stepper */}
      <div className="relative">
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

      {/* Main Content Area */}
      <AnimatePresence mode="wait">
        {step === 'upload' && (
          <motion.div key="upload" variants={fadeVariants} initial="hidden" animate="visible" exit="exit">
            <Card className="rounded-2xl border-none shadow-sm">
              <CardHeader>
                <CardTitle>Select Excel File</CardTitle>
                <CardDescription>
                  Expected columns: Material Code, Quantity, UoM, Warehouse, Date
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`relative flex flex-col items-center justify-center w-full min-h-[300px] border-2 border-dashed rounded-xl cursor-pointer transition-all duration-200 ${
                    isDragging ? 'border-primary bg-primary/5 scale-[1.01]' : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30'
                  }`}
                >
                  <input ref={fileInputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />
                  
                  {previewMutation.isPending ? (
                    <div className="flex flex-col items-center text-primary">
                      <div className="h-12 w-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin mb-4" />
                      <p className="font-medium">Analyzing snapshot...</p>
                    </div>
                  ) : (
                    <>
                      <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4 text-primary">
                        <Upload className="h-8 w-8" />
                      </div>
                      <h3 className="text-xl font-semibold mb-1">Drag & Drop your Excel file</h3>
                      <p className="text-muted-foreground mb-4">or click to browse from your computer</p>
                      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground/70 bg-muted/50 px-3 py-1.5 rounded-full">
                        <FileSpreadsheet className="h-3.5 w-3.5" /> Supports .xlsx and .xls
                      </div>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {step === 'preview' && preview && (
          <motion.div key="preview" variants={fadeVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
            
            {/* Validation Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="rounded-2xl border-none shadow-sm bg-emerald-50/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2 text-emerald-700 font-medium">
                    <div className="p-2 bg-emerald-100 rounded-lg text-emerald-600">
                      <CheckCircle2 className="h-5 w-5" />
                    </div>
                    Row Statistics
                  </div>
                  <div className="grid grid-cols-2 gap-y-2 mt-4 text-sm">
                    <span className="text-muted-foreground">Total Rows:</span>
                    <span className="font-medium">{preview.total_rows}</span>
                    <span className="text-muted-foreground">Valid Rows:</span>
                    <span className="font-semibold text-emerald-700">{preview.valid_rows}</span>
                    <span className="text-muted-foreground">Error Rows:</span>
                    <span className={`font-semibold ${preview.error_rows > 0 ? 'text-destructive' : ''}`}>{preview.error_rows}</span>
                    <span className="text-muted-foreground">Warnings:</span>
                    <span className={`font-semibold ${preview.warning_rows > 0 ? 'text-amber-600' : ''}`}>{preview.warning_rows}</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="rounded-2xl border-none shadow-sm bg-blue-50/50">
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2 text-blue-700 font-medium">
                    <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
                      <FileSpreadsheet className="h-5 w-5" />
                    </div>
                    Inventory Totals
                  </div>
                  <div className="grid grid-cols-2 gap-y-2 mt-4 text-sm">
                    <span className="text-muted-foreground">Total Materials:</span>
                    <span className="font-medium text-blue-900">{preview.total_materials}</span>
                    <span className="text-muted-foreground">Total Quantity:</span>
                    <span className="font-semibold text-blue-900">{parseFloat(preview.total_quantity).toLocaleString()}</span>
                  </div>
                </CardContent>
              </Card>

              <Card className={`rounded-2xl border-none shadow-sm ${(preview.unknown_materials > 0 || preview.negative_quantities > 0) ? 'bg-destructive/10' : 'bg-muted/30'}`}>
                <CardContent className="p-6">
                  <div className="flex items-center gap-3 mb-2 font-medium">
                    <div className="p-2 bg-background rounded-lg text-muted-foreground">
                      <AlertCircle className="h-5 w-5" />
                    </div>
                    Validation Issues
                  </div>
                  <div className="grid grid-cols-2 gap-y-2 mt-4 text-sm">
                    <span className="text-muted-foreground">Duplicates:</span>
                    <span className={`font-medium ${preview.duplicates > 0 ? 'text-amber-600' : ''}`}>{preview.duplicates}</span>
                    <span className="text-muted-foreground">Unknown Mats:</span>
                    <span className={`font-medium ${preview.unknown_materials > 0 ? 'text-destructive' : ''}`}>{preview.unknown_materials}</span>
                    <span className="text-muted-foreground">Negative Qty:</span>
                    <span className={`font-medium ${preview.negative_quantities > 0 ? 'text-destructive' : ''}`}>{preview.negative_quantities}</span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Global Errors & Warnings */}
            {(preview.errors.length > 0 || preview.warnings.length > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {preview.errors.length > 0 && (
                  <Card className="rounded-2xl border-destructive/20 bg-destructive/5 shadow-sm">
                    <CardHeader className="pb-2 px-6 pt-6">
                      <CardTitle className="text-base text-destructive flex items-center gap-2">
                        <AlertCircle className="h-5 w-5" /> Global Errors
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="px-6 pb-6 pt-0">
                      <ul className="space-y-1.5 mt-2">
                        {preview.errors.map((e, i) => <li key={i} className="text-sm text-destructive/80 flex items-start gap-2"><span className="mt-1">•</span>{e}</li>)}
                      </ul>
                    </CardContent>
                  </Card>
                )}
                
                {preview.warnings.length > 0 && (
                  <Card className="rounded-2xl border-amber-200/50 bg-amber-50/50 shadow-sm">
                    <CardHeader className="pb-2 px-6 pt-6">
                      <CardTitle className="text-base text-amber-700 flex items-center gap-2">
                        <AlertCircle className="h-5 w-5" /> Warnings
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="px-6 pb-6 pt-0">
                      <ul className="space-y-1.5 mt-2">
                        {preview.warnings.map((w, i) => <li key={i} className="text-sm text-amber-700/80 flex items-start gap-2"><span className="mt-1">•</span>{w}</li>)}
                      </ul>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}

            {/* Data Table */}
            <Card className="rounded-2xl border-none shadow-sm overflow-hidden flex flex-col max-h-[600px]">
              <CardHeader className="bg-muted/20 border-b pb-4">
                <CardTitle className="text-lg">Data Preview</CardTitle>
                <CardDescription>Review the processed snapshot before committing to the ledger.</CardDescription>
              </CardHeader>
              <div className="overflow-auto flex-1">
                <Table headers={['Row', 'Material', 'Warehouse', 'Qty', 'Status', 'Messages']} isEmpty={preview.rows.length === 0} className="border-0">
                  {preview.rows.map((row) => (
                    <Tr key={row.row} className="hover:bg-muted/30">
                      <Td className="text-muted-foreground w-16 text-center">{row.row}</Td>
                      <Td className="font-mono text-xs font-medium">{row.material_code}</Td>
                      <Td className="font-medium text-sm">{row.warehouse}</Td>
                      <Td>{row.quantity}</Td>
                      <Td>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          row.status === 'valid' ? 'bg-emerald-100 text-emerald-700' :
                          row.status === 'error' ? 'bg-destructive/10 text-destructive' :
                          'bg-amber-100 text-amber-700'
                        }`}>
                          {row.status.toUpperCase()}
                        </span>
                      </Td>
                      <Td className="text-muted-foreground text-xs max-w-[250px] truncate" title={row.messages.join(', ')}>{row.messages.join(', ')}</Td>
                    </Tr>
                  ))}
                </Table>
              </div>
            </Card>

            {/* Action Bar */}
            <div className="flex items-center justify-between pt-4 border-t">
              <Button variant="outline" onClick={() => setStep('upload')} className="rounded-full px-6">
                Back to Upload
              </Button>
              <Button
                onClick={() => file && commitMutation.mutate(file)}
                isLoading={commitMutation.isPending}
                disabled={preview.error_rows > 0 || commitMutation.isPending}
                className="rounded-full px-8 shadow-sm"
                size="lg"
              >
                {preview.error_rows > 0 ? 'Resolve Errors to Commit' : 'Commit Snapshot'}
                {!preview.error_rows && <ChevronRight className="ml-2 h-4 w-4" />}
              </Button>
            </div>
          </motion.div>
        )}

        {step === 'done' && (
          <motion.div key="done" variants={fadeVariants} initial="hidden" animate="visible" exit="exit">
            <Card className="rounded-2xl border-none shadow-sm overflow-hidden relative">
              <div className="absolute top-0 left-0 w-full h-2 bg-emerald-500"></div>
              <CardContent className="p-12 text-center flex flex-col items-center">
                <div className="h-20 w-20 bg-emerald-100 rounded-full flex items-center justify-center mb-6">
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
                  >
                    <CheckCircle2 className="h-10 w-10 text-emerald-600" />
                  </motion.div>
                </div>
                <h3 className="text-2xl font-bold tracking-tight mb-2">Reconciliation Complete</h3>
                <p className="text-muted-foreground max-w-md mx-auto mb-8">
                  Adjustments have been automatically posted to the ledger to match your uploaded snapshot.
                </p>
                <div className="flex gap-4">
                  <Button variant="outline" onClick={() => { setStep('upload'); setFile(null); setPreview(null) }} className="rounded-full px-6">
                    Upload Another Snapshot
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
