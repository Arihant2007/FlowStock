import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { masterApi } from '@/api/master'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Table, Tr, Td } from '@/components/ui/table'
import { formatDateTime } from '@/lib/utils'
import { MetricCard } from '@/components/enterprise/MetricCard'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { TableToolbar } from '@/components/enterprise/TableToolbar'
import { StatusBadge } from '@/components/enterprise/StatusBadge'
import { ActionMenu } from '@/components/enterprise/ActionMenu'
import { History, Upload, FileText, AlertCircle, Eye, CheckCircle } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export function BOMsPage() {
  const { hasPermission } = useAuth()
  const [selectedSession, setSelectedSession] = useState<any | null>(null)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['master', 'boms', 'history'],
    queryFn: () => masterApi.getBOMUploadHistory(),
    enabled: hasPermission('master:read'),
  })

  const allHistory = useMemo(() => data?.data ?? [], [data?.data])

  const history = useMemo(() => {
    return allHistory.filter((session: any) =>
      (session.filename || '').toLowerCase().includes(search.toLowerCase())
    )
  }, [allHistory, search])

  const committedCount = useMemo(
    () => allHistory.filter((s: any) => s.status === 'COMMITTED').length,
    [allHistory]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="BOM Import History"
        subtitle="Audit log of Bill of Materials uploads and SKUs import sessions"
        badgeText={allHistory.length}
      >
        {hasPermission('master:write') && (
          <Link to="/master/bom-upload">
            <Button className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white h-9 text-xs font-semibold shadow-sm">
              <Upload className="mr-1.5 h-3.5 w-3.5" /> Upload BOM Excel
            </Button>
          </Link>
        )}
      </PageHeader>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Import Sessions"
          value={allHistory.length}
          subtext="Excel Files Processed"
          icon={History}
        />
        <MetricCard
          title="Committed Imports"
          value={committedCount}
          subtext="Successful SKU Updates"
          icon={CheckCircle}
          badge={{ text: 'Completed', variant: 'success' }}
        />
        <MetricCard
          title="Active System Recipes"
          value="48 BOMs"
          subtext="ITC Snack Division"
          icon={FileText}
        />
      </div>

      {/* SadaxCart Table Container */}
      <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm overflow-hidden">
        <TableToolbar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search import filename..."
        />

        <Table
          headers={['Import Filename', 'Status', 'Timestamp', 'Created / Updated SKUs', 'Actions']}
          isLoading={isLoading}
          isEmpty={history.length === 0}
          emptyMessage="No import history found matching your search."
          className="border-0 shadow-none rounded-none"
        >
          {history.map((session: any) => (
            <Tr key={session.public_id}>
              <Td className="font-medium text-slate-900">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-slate-400 shrink-0" />
                  <span className="font-semibold text-xs text-slate-900">{session.filename}</span>
                </div>
              </Td>
              <Td>
                <StatusBadge status={session.status} />
              </Td>
              <Td className="text-slate-500 text-xs">{formatDateTime(session.created_at)}</Td>
              <Td>
                {session.status === 'COMMITTED' && session.import_results ? (
                  <div className="flex items-center gap-3 text-xs text-slate-600 font-medium">
                    <span>
                      <strong className="text-slate-900">{session.import_results.skus_created || 0}</strong> Created
                    </span>
                    <span>
                      <strong className="text-slate-900">{session.import_results.skus_updated || 0}</strong> Updated
                    </span>
                  </div>
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </Td>
              <Td>
                <ActionMenu
                  items={[
                    {
                      label: 'View Import Audit',
                      icon: Eye,
                      onClick: () => setSelectedSession(session),
                    },
                  ]}
                />
              </Td>
            </Tr>
          ))}
        </Table>
      </div>

      {/* Details Modal */}
      <Dialog open={!!selectedSession} onOpenChange={(v) => !v && setSelectedSession(null)}>
        <DialogContent className="max-w-2xl rounded-2xl border-slate-100 p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl font-bold text-slate-900">
              <FileText className="h-5 w-5 text-blue-600" />
              Import Session Audit
            </DialogTitle>
          </DialogHeader>

          {selectedSession && (
            <div className="space-y-6 pt-2">
              <div className="grid grid-cols-2 gap-4 text-xs bg-slate-50 p-4 rounded-xl border border-slate-100">
                <div>
                  <p className="text-slate-500 mb-1">Target Filename</p>
                  <p className="font-semibold text-slate-900 text-sm">{selectedSession.filename}</p>
                </div>
                <div>
                  <p className="text-slate-500 mb-1">Session Status</p>
                  <StatusBadge status={selectedSession.status} />
                </div>
                <div>
                  <p className="text-slate-500 mb-1">Import Timestamp</p>
                  <p className="font-medium text-slate-900">{formatDateTime(selectedSession.created_at)}</p>
                </div>
                <div>
                  <p className="text-slate-500 mb-1">Processing Duration</p>
                  <p className="font-medium text-slate-900">
                    {selectedSession.import_results?.duration_seconds
                      ? `${selectedSession.import_results.duration_seconds.toFixed(2)}s`
                      : '—'}
                  </p>
                </div>
              </div>

              {selectedSession.status === 'COMMITTED' && selectedSession.import_results && (
                <div className="space-y-3">
                  <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider">Commit Summary</h4>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-blue-50/60 p-3 rounded-xl border border-blue-100 text-center">
                      <p className="text-xl font-bold text-blue-700">{selectedSession.import_results.skus_created}</p>
                      <p className="text-[10px] font-semibold text-blue-600/80 uppercase tracking-wider">SKUs Created</p>
                    </div>
                    <div className="bg-emerald-50/60 p-3 rounded-xl border border-emerald-100 text-center">
                      <p className="text-xl font-bold text-emerald-700">{selectedSession.import_results.skus_updated}</p>
                      <p className="text-[10px] font-semibold text-emerald-600/80 uppercase tracking-wider">SKUs Updated</p>
                    </div>
                    <div className="bg-amber-50/60 p-3 rounded-xl border border-amber-100 text-center">
                      <p className="text-xl font-bold text-amber-700">{selectedSession.import_results.bom_versions_created}</p>
                      <p className="text-[10px] font-semibold text-amber-600/80 uppercase tracking-wider">BOM Versions</p>
                    </div>
                  </div>
                </div>
              )}

              {selectedSession.warnings && selectedSession.warnings.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-bold text-amber-800 text-xs flex items-center gap-1.5">
                    <AlertCircle className="h-4 w-4" /> Warnings Recorded ({selectedSession.warnings.length})
                  </h4>
                  <div className="bg-amber-50 rounded-xl p-3.5 max-h-40 overflow-y-auto text-xs text-amber-900 border border-amber-200/60">
                    <ul className="list-disc pl-4 space-y-1">
                      {selectedSession.warnings.map((w: string, i: number) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
