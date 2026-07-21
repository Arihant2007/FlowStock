import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getErrorMessage } from '@/lib/utils'
import { Upload, CheckCircle, XCircle, AlertCircle, FileSpreadsheet, ArrowRight, Download } from 'lucide-react'
import type { MaterialUploadPreview } from '@/types/api'

export function MaterialUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<MaterialUploadPreview | null>(null)
  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload')

  const previewMutation = useMutation({
    mutationFn: (f: File) => masterApi.previewMaterialUpload(f),
    onSuccess: (data) => {
      setPreview(data.data)
      setStep('preview')
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const commitMutation = useMutation({
    mutationFn: (f: File) => masterApi.commitMaterialUpload(f),
    onSuccess: (data) => {
      const { created, updated, skipped } = data.data as any;
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
    } catch (err) {
      toast.error('Failed to download template')
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setPreview(null); setStep('upload') }
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
      e.target.value = '' // Reset input
    }
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-5xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileSpreadsheet className="h-6 w-6" /> Material Master Upload
          </h1>
          <p className="text-muted-foreground text-sm">Upload an Excel file to create or update Materials</p>
        </div>
        <div className="flex gap-2">
          <div className="flex items-center">
            <Button variant="secondary" className="bg-amber-100 text-amber-800 hover:bg-amber-200 flex items-center gap-2 cursor-pointer" type="button" onClick={() => document.getElementById('bom-gen-input')?.click()}>
              <FileSpreadsheet className="h-4 w-4" /> Generate from BOM
            </Button>
            <input id="bom-gen-input" type="file" accept=".xlsx,.xls" className="hidden" onChange={handleGenerateFromBOM} />
          </div>
          <Button variant="outline" onClick={handleDownloadTemplate} className="flex items-center gap-2">
            <Download className="h-4 w-4" /> Download Empty Template
          </Button>
        </div>
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
              Expected columns: Material Code, Material Name, UOM, Category, Material Type, Group
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
          <div className="grid grid-cols-4 gap-4">
            <Card className="border-green-200 bg-green-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <div>
                    <p className="text-2xl font-bold text-green-700">{preview.valid_rows}</p>
                    <p className="text-xs text-green-600">Valid (New/Update)</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-amber-200 bg-amber-50">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-amber-600" />
                  <div>
                    <p className="text-2xl font-bold text-amber-700">{preview.skipped_rows_count}</p>
                    <p className="text-xs text-amber-600">Skipped (No Changes)</p>
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

          <div className="grid grid-cols-2 gap-4">
             <Card>
               <CardHeader className="pb-2"><CardTitle className="text-sm">Summary</CardTitle></CardHeader>
               <CardContent className="pt-0 text-sm space-y-1">
                 <div className="flex justify-between"><span>New Materials:</span> <span className="font-medium">{preview.new_materials.length}</span></div>
                 <div className="flex justify-between"><span>Updated Materials:</span> <span className="font-medium">{preview.updated_materials.length}</span></div>
                 <div className="flex justify-between"><span>Duplicate Codes:</span> <span className="font-medium">{preview.duplicate_material_codes.length}</span></div>
                 <div className="flex justify-between"><span>Invalid FK Rows:</span> <span className="font-medium">{preview.invalid_rows.length}</span></div>
               </CardContent>
             </Card>
          </div>

          {/* Errors */}
          {preview.errors.length > 0 && (
            <Card className="border-red-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-red-700 flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4" /> Global Errors
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-1">
                  {preview.errors.map((e, i) => <li key={i} className="text-sm text-red-600">• {e}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Warnings */}
          {preview.warnings && preview.warnings.length > 0 && (
            <Card className="border-amber-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-amber-700 flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4" /> Warnings
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-1">
                  {preview.warnings.map((w, i) => <li key={i} className="text-sm text-amber-600">• {w}</li>)}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Rows preview */}
          <Card>
            <CardContent className="pt-4 pb-0">
              <Table headers={['Row', 'Code', 'Name', 'UOM', 'Cat', 'Type', 'Status', 'Message']} isEmpty={preview.rows.length === 0}>
                {preview.rows.map((row) => (
                  <Tr key={row.row_number}>
                    <Td>{row.row_number}</Td>
                    <Td className="font-mono">{row.material_code}</Td>
                    <Td>{row.material_name}</Td>
                    <Td>{row.uom}</Td>
                    <Td>{row.category}</Td>
                    <Td>{row.material_type}</Td>
                    <Td>
                      <Badge
                        label={row.status}
                        className={
                          row.status === 'valid' ? 'bg-green-100 text-green-800' :
                          row.status === 'skipped' ? 'bg-amber-100 text-amber-800' :
                          'bg-red-100 text-red-800'
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
            <p className="text-green-700 text-sm mt-1">Material Master data has been updated in the system.</p>
            <Button variant="outline" className="mt-4" onClick={() => { setStep('upload'); setFile(null); setPreview(null) }}>
              Upload Another
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
