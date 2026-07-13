import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getErrorMessage } from '@/lib/utils'
import { Upload, CheckCircle, XCircle, AlertCircle, FileSpreadsheet, ArrowRight } from 'lucide-react'
import type { BOMUploadPreview } from '@/types/api'

export function BOMUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<BOMUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload')

  const previewMutation = useMutation({
    mutationFn: (f: File) => masterApi.previewBOMUpload(f),
    onSuccess: (data) => {
      setPreview(data.data)
      setStep('preview')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const commitMutation = useMutation({
    mutationFn: (f: File) => masterApi.commitBOMUpload(f),
    onSuccess: (data) => {
      toast.success(`BOM uploaded! ${(data.data as { skus_updated: number }).skus_updated} SKU(s) updated.`)
      setStep('done')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setPreview(null); setStep('upload') }
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
                onClick={() => previewMutation.mutate(file)}
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
          <div className="grid grid-cols-3 gap-4">
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
            <Card className="border-red-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-red-700 flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4" /> Errors
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-1">
                  {preview.errors.map((e, i) => <li key={i} className="text-sm text-red-600">• {e}</li>)}
                </ul>
              </CardContent>
            </Card>
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
                        label={row.status}
                        className={
                          row.status === 'valid' ? 'bg-green-100 text-green-800' :
                          row.status === 'error' ? 'bg-red-100 text-red-800' :
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

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setStep('upload')}>Back</Button>
            <Button
              onClick={() => file && commitMutation.mutate(file)}
              isLoading={commitMutation.isPending}
              disabled={preview.error_rows > 0}
            >
              {preview.error_rows > 0 ? 'Fix errors to continue' : 'Commit Upload'}
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Done */}
      {step === 'done' && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-8 pb-8 text-center">
            <CheckCircle className="h-12 w-12 text-green-600 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-green-800">Upload Successful</h3>
            <p className="text-green-700 text-sm mt-1">BOM data has been updated in the system.</p>
            <Button variant="outline" className="mt-4" onClick={() => { setStep('upload'); setFile(null); setPreview(null) }}>
              Upload Another
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
