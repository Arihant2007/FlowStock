import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getErrorMessage } from '@/lib/utils'
import { Upload, CheckCircle, XCircle, AlertCircle, FileSpreadsheet, ArrowRight, Download, ChevronRight } from 'lucide-react'
import type { BOMUploadPreview } from '@/types/api'

function CollapsibleCard({ title, count, children, defaultExpanded = false, icon: Icon, colorClass, borderClass, bgClass = "" }: any) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  return (
    <Card className={`${borderClass} ${bgClass} flex flex-col`}>
      <CardHeader 
        className="pb-2 pt-3 shrink-0 cursor-pointer flex flex-row items-center justify-between select-none hover:bg-black/5 transition-colors" 
        onClick={() => setExpanded(!expanded)}
      >
        <CardTitle className={`text-sm ${colorClass} flex items-center gap-1.5`}>
          <Icon className="h-4 w-4" /> {title} ({count})
        </CardTitle>
        <div className={`transform transition-transform duration-200 ${colorClass} ${expanded ? 'rotate-90' : 'rotate-0'}`}>
          <ChevronRight className="h-4 w-4" />
        </div>
      </CardHeader>
      <div className={`transition-all duration-300 ease-in-out overflow-hidden flex flex-col min-h-0 ${expanded ? 'max-h-[300px] opacity-100' : 'max-h-0 opacity-0'}`}>
        {children}
      </div>
    </Card>
  )
}
function formatMessage(msg: string) {
  const match = msg.match(/Sheet '[^']+', Row (\d+): (.*)/)
  if (match) {
    return <><span className="font-semibold opacity-75">Row {match[1]}</span> &ndash; {match[2]}</>
  }
  return msg
}

function ExpandableList({ items, renderItem, className, limit = 20, buttonClass }: { items: string[], renderItem: (item: string, i: number) => React.ReactNode, className?: string, limit?: number, buttonClass?: string }) {
  const [showAll, setShowAll] = useState(false)
  const displayed = showAll ? items : items.slice(0, limit)
  
  return (
    <>
      <ul className={className}>
        {displayed.map(renderItem)}
      </ul>
      {items.length > limit && (
        <div className="pt-2 sticky bottom-0 pb-1 mt-auto bg-inherit">
          <Button variant="outline" size="sm" className={`h-7 text-xs w-full bg-white/50 backdrop-blur-sm ${buttonClass}`} onClick={() => setShowAll(!showAll)}>
            {showAll ? 'Show Less' : `Show All (${items.length - limit} more)`}
          </Button>
        </div>
      )}
    </>
  )
}

export function BOMUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<BOMUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'pending_session' | 'preview' | 'done'>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [commitResult, setCommitResult] = useState<any>(null)
  
  useEffect(() => {
    const savedSession = sessionStorage.getItem('bomUploadSessionId')
    if (savedSession) {
      setSessionId(savedSession)
      setStep('pending_session')
    }
  }, [])


  const previewMutation = useMutation({
    mutationFn: (params: { file?: File, sessionId?: string }) => masterApi.previewBOMUpload(params),
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
      // Invalidate SKU options + full SKU list so dropdowns reflect new SKUs immediately
      qc.invalidateQueries({ queryKey: ['master', 'skus'] })
      qc.invalidateQueries({ queryKey: ['master', 'skuOptions'] })
      // Refresh dashboard SKU/BOM counters
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
    }
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setPreview(null); setStep('upload') }
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

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileSpreadsheet className="h-6 w-6" /> BOM Upload
        </h1>
        <p className="text-muted-foreground text-sm">Upload an Excel file to create or update Bills of Materials</p>
      </div>

      {/* Progress */}
      <div className="flex items-center gap-2 text-sm">
        {['Upload', 'Preview', 'Done'].map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors ${
              step === s.toLowerCase() ? 'bg-primary text-primary-foreground' :
              (i < ['upload', 'preview', 'done'].indexOf(step)) ? 'bg-green-500 text-white' :
              'bg-muted text-muted-foreground'
            }`}>
              {i < ['upload', 'preview', 'done'].indexOf(step) ? '✓' : i + 1}
            </div>
            <span className={step === s.toLowerCase() ? 'font-medium' : 'text-muted-foreground'}>{s}</span>
            {i < 2 && <ArrowRight className="h-4 w-4 text-muted-foreground" />}
          </div>
        ))}
      </div>

      {/* Pending Session Step */}
      {step === 'pending_session' && (
        <Card>
          <CardHeader>
            <CardTitle>Pending Upload Found</CardTitle>
            <CardDescription>You have an unfinished BOM upload session.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-3">
              <Button onClick={() => previewMutation.mutate({ sessionId: sessionId! })} isLoading={previewMutation.isPending}>
                Resume Upload
              </Button>
              <Button variant="outline" onClick={handleReplace} isLoading={cancelMutation.isPending}>
                Discard & Start New
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 1: Upload */}
      {step === 'upload' && (
        <Card>
          <CardHeader>
            <CardTitle>Select Excel File</CardTitle>
            <CardDescription>
              Expected columns: SKU Code, Material Code, Quantity Per Unit, Material Type (RM/PM)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer hover:bg-muted/30 transition-colors">
              <Upload className="h-8 w-8 text-muted-foreground mb-2" />
              <span className="text-sm text-muted-foreground">
                {file ? file.name : 'Click to select or drag & drop an Excel file'}
              </span>
              <span className="text-xs text-muted-foreground mt-1">.xlsx, .xls</span>
              <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />
            </label>
            {file && (
              <Button
                onClick={() => previewMutation.mutate({ file })}
                isLoading={previewMutation.isPending}
                className="w-full"
              >
                Preview Upload
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 2: Preview */}
      {step === 'preview' && preview && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            <Card className="border-green-200 bg-green-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <div>
                    <p className="text-2xl font-bold text-green-700">{preview.valid_rows}</p>
                    <p className="text-xs text-green-600">Valid rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <XCircle className="h-5 w-5 text-red-600" />
                  <div>
                    <p className="text-2xl font-bold text-red-700">{preview.error_rows}</p>
                    <p className="text-xs text-red-600">Error rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 text-amber-600" />
                  <div>
                    <p className="text-2xl font-bold text-amber-700">{preview.pending_rows ?? 0}</p>
                    <p className="text-xs text-amber-600">Pending Materials</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{preview.total_rows}</p>
                    <p className="text-xs text-muted-foreground">Total rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Errors */}
          {preview.errors.length > 0 && (
            <CollapsibleCard 
              title="Errors" 
              count={preview.errors.length} 
              defaultExpanded={true} 
              icon={AlertCircle} 
              colorClass="text-red-700" 
              borderClass="border-red-200"
            >
              <CardContent className="pt-0 overflow-y-auto min-h-0 custom-scrollbar [&::-webkit-scrollbar-thumb]:bg-red-200 hover:[&::-webkit-scrollbar-thumb]:bg-red-300 relative">
                <ExpandableList 
                  items={preview.errors} 
                  className="space-y-1 pl-4 list-disc text-sm text-red-700 mt-2"
                  buttonClass="text-red-700 hover:text-red-800 border-red-200 hover:bg-red-100"
                  renderItem={(e: any, i: number) => <li key={i}>{formatMessage(e)}</li>} 
                />
              </CardContent>
            </CollapsibleCard>
          )}          {/* Warnings Grouped */}
          {preview.warnings && preview.warnings.length > 0 && (
            <CollapsibleCard 
              title="Warnings" 
              count={preview.warnings.length} 
              defaultExpanded={false} 
              icon={AlertCircle} 
              colorClass="text-amber-700" 
              borderClass="border-amber-200"
            >
              <CardContent className="pt-0 overflow-y-auto min-h-0 custom-scrollbar [&::-webkit-scrollbar-thumb]:bg-amber-200 hover:[&::-webkit-scrollbar-thumb]:bg-amber-300 relative">
                <ExpandableList 
                  items={preview.warnings} 
                  className="space-y-1 pl-4 list-disc text-amber-700 text-sm mt-2"
                  buttonClass="text-amber-800 hover:text-amber-900 border-amber-200 hover:bg-amber-100"
                  renderItem={(w: any, i: number) => <li key={i}>{formatMessage(w)}</li>} 
                />
              </CardContent>
            </CollapsibleCard>
          )}

          {/* Rows preview */}
          <Card>
            <CardContent className="pt-4 pb-0">
              <Table headers={['Row', 'SKU Code', 'Material Code', 'Qty/Unit', 'Status', 'Message']} isEmpty={preview.rows.length === 0}>
                {preview.rows.map((row) => (
                  <Tr key={row.row_number}>
                    <Td>{row.row_number}</Td>
                    <Td className="font-mono">{row.sku_code}</Td>
                    <Td className="font-mono">{row.material_code}</Td>
                    <Td>{row.quantity_per_unit}</Td>
                    <Td>
                      <Badge
                        label={row.status === 'pending_material' ? 'Pending Material' : row.status}
                        className={
                          row.status === 'valid' ? 'bg-green-100 text-green-800' :
                          row.status === 'error' ? 'bg-red-100 text-red-800' :
                          row.status === 'pending_material' ? 'bg-amber-100 text-amber-800' :
                          'bg-amber-100 text-amber-800'
                        }
                      />
                    </Td>
                    <Td className="text-muted-foreground text-xs">{row.message}</Td>
                  </Tr>
                ))}
              </Table>
            </CardContent>
          </Card>

          {/* Actions & Extraction Summary */}
          <div className="flex flex-col gap-4">
            {preview.unknown_materials?.length > 0 && (
              <Card className="bg-amber-50/50 border-amber-200">
                <CardContent className="pt-4 flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="space-y-1 text-sm text-amber-900">
                    <p className="font-semibold text-base flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" /> Generate Missing Materials
                    </p>
                    <div className="grid grid-cols-2 gap-x-8 gap-y-1">
                      <span>Unique Materials Found:</span>
                      <span className="font-medium text-right">{new Set(preview.rows.filter(r => r.material_code).map(r => r.material_code)).size}</span>
                      <span>Already Exist:</span>
                      <span className="font-medium text-right">
                        {new Set(preview.rows.filter(r => r.material_code).map(r => r.material_code)).size - preview.unknown_materials.length}
                      </span>
                      <span className="font-semibold">Need Import:</span>
                      <span className="font-bold text-amber-700 text-right">{preview.unknown_materials.length}</span>
                    </div>
                    <p className="text-xs text-amber-800 mt-2">
                      <strong>Workflow:</strong> 1. Download Template → 2. Complete Excel → 3. Upload to Material Master → 4. Click "Resume BOM Import"
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    className="bg-amber-100 text-amber-800 hover:bg-amber-200 shrink-0"
                    onClick={async () => {
                      if (!file && !sessionId) return;
                      try {
                        const blob = await masterApi.extractMaterialsFromBOM(null, sessionId, true);
                        const url = window.URL.createObjectURL(new Blob([blob]));
                        const link = document.createElement('a');
                        link.href = url;
                        link.setAttribute('download', 'extracted_materials.xlsx');
                        document.body.appendChild(link);
                        link.click();
                        link.remove();
                        toast.success('Generated template downloaded. Fill it and upload to Material Master.');
                      } catch (e: any) {
                        console.error('Extraction failed:', e);
                        toast.error(`Failed to generate template: ${getErrorMessage(e) || e.message}`);
                      }
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download Material Master
                  </Button>
                </CardContent>
              </Card>
            )}

            <div className="flex gap-3 items-center">
              <Button variant="outline" onClick={handleReplace}>Cancel</Button>
              <Button
                onClick={() => {
                  if (preview.session_status === 'WAITING_FOR_MATERIALS') {
                    sessionId && previewMutation.mutate({ sessionId })
                  } else {
                    sessionId && commitMutation.mutate(sessionId)
                  }
                }}
                isLoading={commitMutation.isPending || previewMutation.isPending}
                disabled={preview.session_status !== 'READY_TO_COMMIT' && preview.session_status !== 'WAITING_FOR_MATERIALS'}
              >
                {preview.session_status === 'WAITING_FOR_MATERIALS' ? 'Resume BOM Import' : 'Commit Upload'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Done */}
      {step === 'done' && commitResult && (
        <Card className="border-green-200">
          <CardHeader className="bg-green-50/50 pb-4 border-b border-green-100">
            <CardTitle className="text-lg font-semibold text-green-800 flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              BOM Import Completed Successfully
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6 space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-muted/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-primary">{commitResult.skus_created}</p>
                <p className="text-xs text-muted-foreground uppercase tracking-wider mt-1">SKUs Created</p>
              </div>
              <div className="bg-muted/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-primary">{commitResult.skus_updated}</p>
                <p className="text-xs text-muted-foreground uppercase tracking-wider mt-1">SKUs Updated</p>
              </div>
              <div className="bg-muted/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-primary">{commitResult.bom_versions_created}</p>
                <p className="text-xs text-muted-foreground uppercase tracking-wider mt-1">BOM Versions</p>
              </div>
              <div className="bg-muted/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-primary">{commitResult.items_created}</p>
                <p className="text-xs text-muted-foreground uppercase tracking-wider mt-1">BOM Items</p>
              </div>
            </div>

            <div className="flex justify-between items-center text-sm border-t pt-4">
              <span className="text-muted-foreground">
                <b className="text-foreground">{commitResult.materials_referenced}</b> Materials Referenced
              </span>
              <span className="text-muted-foreground">
                Duration: <b className="text-foreground">{commitResult.duration_seconds?.toFixed(2)}s</b>
              </span>
            </div>

            {commitResult.warnings && commitResult.warnings.length > 0 && (
              <CollapsibleCard 
                title="Warnings" 
                count={commitResult.warnings.length} 
                defaultExpanded={false} 
                icon={AlertCircle} 
                colorClass="text-amber-800" 
                borderClass="border-amber-100"
                bgClass="bg-amber-50"
              >
                <div className="overflow-y-auto min-h-0 custom-scrollbar [&::-webkit-scrollbar-thumb]:bg-amber-200 hover:[&::-webkit-scrollbar-thumb]:bg-amber-300 relative p-4 pt-0">
                  <ExpandableList 
                    items={commitResult.warnings} 
                    className="text-sm text-amber-700 list-disc pl-5 mt-2"
                    buttonClass="text-amber-800 hover:text-amber-900 border-amber-200 hover:bg-amber-100"
                    renderItem={(w: any, i: number) => <li key={i}>{formatMessage(w)}</li>} 
                  />
                </div>
              </CollapsibleCard>
            )}

            <div className="flex gap-3 pt-2">
              <Button onClick={() => { setStep('upload'); setFile(null); setPreview(null); setCommitResult(null) }}>
                Upload Another BOM
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
