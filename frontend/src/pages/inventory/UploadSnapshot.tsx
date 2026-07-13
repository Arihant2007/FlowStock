import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { inventoryApi } from '@/api/inventory'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getErrorMessage } from '@/lib/utils'
import { Upload, CheckCircle, XCircle, AlertCircle, FileSpreadsheet, ArrowRight } from 'lucide-react'
import type { OpeningBalanceUploadPreview } from '@/types/api'

export function InventoryUploadPage() {
  const qc = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<OpeningBalanceUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload')

  const previewMutation = useMutation({
    mutationFn: (f: File) => inventoryApi.previewUpload(f),
    onSuccess: (data) => {
      setPreview(data.data)
      setStep('preview')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const commitMutation = useMutation({
    mutationFn: (f: File) => inventoryApi.commitUpload(f, true), // Passing ignoreWarnings=true for UI simplicity
    onSuccess: (data) => {
      const res = data.data as any
      toast.success(`Inventory updated! ${res.adjustments_created} adjustment(s) created.`)
      qc.invalidateQueries({ queryKey: ['inventory'] })
      setStep('done')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setPreview(null); setStep('upload') }
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Upload className="h-6 w-6" /> Inventory Snapshot Upload
        </h1>
        <p className="text-muted-foreground text-sm">Upload daily closing balances to reconcile the system ledger</p>
      </div>

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

      {step === 'upload' && (
        <Card>
          <CardHeader>
            <CardTitle>Select Excel File</CardTitle>
            <CardDescription>
              Expected columns: Material Code, Quantity, UoM, Warehouse, Date
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer hover:bg-muted/30 transition-colors">
              <FileSpreadsheet className="h-8 w-8 text-muted-foreground mb-2" />
              <span className="text-sm text-muted-foreground">
                {file ? file.name : 'Click to select or drag & drop an Excel file'}
              </span>
              <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleFileChange} />
            </label>
            {file && (
              <Button
                onClick={() => previewMutation.mutate(file)}
                isLoading={previewMutation.isPending}
                className="w-full"
              >
                Preview Snapshot
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {step === 'preview' && preview && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <Card className="border-green-200 bg-green-50">
              <CardContent className="pt-4 flex items-center gap-3">
                <CheckCircle className="h-6 w-6 text-green-600" />
                <div><p className="text-2xl font-bold text-green-700">{preview.valid_rows}</p><p className="text-xs text-green-600">Valid</p></div>
              </CardContent>
            </Card>
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-4 flex items-center gap-3">
                <AlertCircle className="h-6 w-6 text-amber-600" />
                <div><p className="text-2xl font-bold text-amber-700">{preview.warning_rows}</p><p className="text-xs text-amber-600">Warnings</p></div>
              </CardContent>
            </Card>
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-4 flex items-center gap-3">
                <XCircle className="h-6 w-6 text-red-600" />
                <div><p className="text-2xl font-bold text-red-700">{preview.error_rows}</p><p className="text-xs text-red-600">Errors</p></div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 flex items-center gap-3">
                <FileSpreadsheet className="h-6 w-6 text-muted-foreground" />
                <div><p className="text-2xl font-bold">{preview.total_rows}</p><p className="text-xs text-muted-foreground">Total</p></div>
              </CardContent>
            </Card>
          </div>

          {(preview.errors.length > 0 || preview.warnings.length > 0) && (
            <Card className={preview.errors.length > 0 ? "border-red-200" : "border-amber-200"}>
              <CardContent className="pt-4 space-y-2">
                {preview.errors.map((e, i) => <p key={i} className="text-sm text-red-600 font-medium">• {e}</p>)}
                {preview.warnings.map((w, i) => <p key={i} className="text-sm text-amber-600 font-medium">• {w}</p>)}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent className="pt-4 pb-0">
              <Table headers={['Row', 'Material', 'Warehouse', 'Qty', 'Status', 'Messages']} isEmpty={preview.rows.length === 0}>
                {preview.rows.map((row) => (
                  <Tr key={row.row}>
                    <Td>{row.row}</Td>
                    <Td className="font-mono">{row.material_code}</Td>
                    <Td>{row.warehouse}</Td>
                    <Td>{row.quantity}</Td>
                    <Td>
                      <Badge
                        label={row.status}
                        className={
                          row.status === 'valid' ? 'bg-green-100 text-green-800' :
                          row.status === 'error' ? 'bg-red-100 text-red-800' :
                          'bg-amber-100 text-amber-800'
                        }
                      />
                    </Td>
                    <Td className="text-xs text-muted-foreground max-w-xs truncate">{row.messages.join(', ')}</Td>
                  </Tr>
                ))}
              </Table>
            </CardContent>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setStep('upload')}>Back</Button>
            <Button
              onClick={() => file && commitMutation.mutate(file)}
              isLoading={commitMutation.isPending}
              disabled={preview.error_rows > 0}
            >
              {preview.error_rows > 0 ? 'Fix errors to continue' : 'Commit Snapshot'}
            </Button>
          </div>
        </div>
      )}

      {step === 'done' && (
        <Card className="border-green-200 bg-green-50 text-center py-12">
          <CheckCircle className="h-16 w-16 text-green-600 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-green-800">Reconciliation Complete</h3>
          <p className="text-green-700 mt-2">Adjustments have been posted to match the uploaded snapshot.</p>
          <Button variant="outline" className="mt-6" onClick={() => { setStep('upload'); setFile(null); setPreview(null) }}>
            Upload Another
          </Button>
        </Card>
      )}
    </div>
  )
}
