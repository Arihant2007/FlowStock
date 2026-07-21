import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { masterApi } from '@/api/master'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { formatDateTime } from '@/lib/utils'
import { History, Upload, FileText, AlertCircle, Eye } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export function BOMsPage() {
  const { hasPermission } = useAuth()
  const [selectedSession, setSelectedSession] = useState<any | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['master', 'boms', 'history'],
    queryFn: () => masterApi.getBOMUploadHistory(),
    enabled: hasPermission('master:read'),
  })

  const history = data?.data ?? []

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <History className="h-6 w-6" /> Import History
          </h1>
          <p className="text-muted-foreground text-sm">History of Bill of Materials uploads</p>
        </div>
        {hasPermission('master:write') && (
          <Link to="/master/bom-upload">
            <Button className="flex items-center gap-2">
              <Upload className="h-4 w-4" /> Upload BOM
            </Button>
          </Link>
        )}
      </div>

      <Card>
        <CardContent className="pt-4 pb-0">
          <Table
            headers={['Filename', 'Status', 'Date', 'Stats', 'Actions']}
            isLoading={isLoading}
            isEmpty={history.length === 0}
            emptyMessage="No import history found."
          >
            {history.map((session: any) => (
              <Tr key={session.public_id}>
                <Td className="font-medium">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span>{session.filename}</span>
                  </div>
                </Td>
                <Td>
                  <Badge label={session.status} variant="status" />
                </Td>
                <Td className="text-muted-foreground">
                  {formatDateTime(session.created_at)}
                </Td>
                <Td>
                  {session.status === 'COMMITTED' && session.import_results ? (
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span><b className="text-foreground">{session.import_results.skus_created || 0}</b> SKUs Created</span>
                      <span><b className="text-foreground">{session.import_results.skus_updated || 0}</b> SKUs Updated</span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </Td>
                <Td>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="flex items-center gap-1.5"
                    onClick={() => setSelectedSession(session)}
                  >
                    <Eye className="h-4 w-4" />
                    <span>View Details</span>
                  </Button>
                </Td>
              </Tr>
            ))}
          </Table>
        </CardContent>
      </Card>

      {/* Import Details Modal */}
      <Dialog open={!!selectedSession} onOpenChange={(v) => !v && setSelectedSession(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Import Details
            </DialogTitle>
          </DialogHeader>
          
          {selectedSession && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground mb-1">Filename</p>
                  <p className="font-medium">{selectedSession.filename}</p>
                </div>
                <div>
                  <p className="text-muted-foreground mb-1">Status</p>
                  <Badge label={selectedSession.status} variant="status" />
                </div>
                <div>
                  <p className="text-muted-foreground mb-1">Imported At</p>
                  <p className="font-medium">{formatDateTime(selectedSession.created_at)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground mb-1">Duration</p>
                  <p className="font-medium">
                    {selectedSession.import_results?.duration_seconds 
                      ? `${selectedSession.import_results.duration_seconds.toFixed(2)}s` 
                      : '—'}
                  </p>
                </div>
              </div>

              {selectedSession.status === 'COMMITTED' && selectedSession.import_results && (
                <>
                  <div className="border-t pt-4">
                    <h3 className="font-semibold mb-3">Commit Summary</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-muted/50 p-3 rounded-lg text-center">
                        <p className="text-2xl font-bold text-primary">{selectedSession.import_results.skus_created}</p>
                        <p className="text-xs text-muted-foreground uppercase tracking-wider">SKUs Created</p>
                      </div>
                      <div className="bg-muted/50 p-3 rounded-lg text-center">
                        <p className="text-2xl font-bold text-primary">{selectedSession.import_results.skus_updated}</p>
                        <p className="text-xs text-muted-foreground uppercase tracking-wider">SKUs Updated</p>
                      </div>
                      <div className="bg-muted/50 p-3 rounded-lg text-center">
                        <p className="text-2xl font-bold text-primary">{selectedSession.import_results.bom_versions_created}</p>
                        <p className="text-xs text-muted-foreground uppercase tracking-wider">BOM Versions</p>
                      </div>
                      <div className="bg-muted/50 p-3 rounded-lg text-center">
                        <p className="text-2xl font-bold text-primary">{selectedSession.import_results.items_created}</p>
                        <p className="text-xs text-muted-foreground uppercase tracking-wider">BOM Items</p>
                      </div>
                      <div className="bg-muted/50 p-3 rounded-lg text-center">
                        <p className="text-2xl font-bold text-primary">{selectedSession.import_results.materials_referenced}</p>
                        <p className="text-xs text-muted-foreground uppercase tracking-wider">Materials Referenced</p>
                      </div>
                    </div>
                  </div>

                  {selectedSession.warnings && selectedSession.warnings.length > 0 && (
                    <div className="border-t pt-4">
                      <h3 className="font-semibold flex items-center gap-2 mb-3 text-amber-700">
                        <AlertCircle className="h-4 w-4" />
                        Warnings ({selectedSession.warnings.length})
                      </h3>
                      <div className="bg-amber-50 rounded-lg p-3 max-h-48 overflow-y-auto text-sm text-amber-900">
                        <ul className="list-disc pl-5 space-y-1">
                          {selectedSession.warnings.map((w: string, i: number) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
