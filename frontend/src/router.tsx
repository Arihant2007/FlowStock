import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { AppLayout } from '@/layouts/AppLayout'
import { Loader2 } from 'lucide-react'

// Pages
import { LoginPage } from '@/pages/Login'
import { DashboardPage } from '@/pages/Dashboard'
import { WarehousesPage } from '@/pages/master/Warehouses'
import { MaterialsPage } from '@/pages/master/Materials'
import { MaterialUploadPage } from '@/pages/master/MaterialUpload'
import { SKUsPage } from '@/pages/master/SKUs'
import { BOMUploadPage } from '@/pages/master/BOMUpload'
import { BOMsPage } from '@/pages/master/BOMs'
import { InventoryBalancesPage } from '@/pages/inventory/Balances'
import { InventoryUploadPage } from '@/pages/inventory/UploadSnapshot'
import { EODCountPage } from '@/pages/inventory/EODCount'
import { TransactionHistoryPage } from '@/pages/inventory/TransactionHistory'
import { VarianceReportPage } from '@/pages/inventory/VarianceReport'
import { NewRequestPage } from '@/pages/ods/NewRequest'
import { ODSRequestsPage } from '@/pages/ods/Requests'
import { RMPMRequestsPage } from '@/pages/rmpm/Requests'
import { RMPMRequestDetailPage } from '@/pages/rmpm/RequestDetail'
import { ReportsInventoryPage } from '@/pages/reports/Inventory'
import { ReportsRequestsPage } from '@/pages/reports/Requests'
import { ReportsTransactionsPage } from '@/pages/reports/Transactions'
import { RequirePermission } from '@/components/RequirePermission'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          {/* Master */}
          <Route path="master/warehouses" element={<RequirePermission permission="master:read"><WarehousesPage /></RequirePermission>} />
          <Route path="master/materials" element={<RequirePermission permission="master:read"><MaterialsPage /></RequirePermission>} />
          <Route path="master/material-upload" element={<RequirePermission permission="master:write"><MaterialUploadPage /></RequirePermission>} />
          <Route path="master/skus" element={<RequirePermission permission="master:read"><SKUsPage /></RequirePermission>} />
          <Route path="master/boms" element={<RequirePermission permission="master:read"><BOMsPage /></RequirePermission>} />
          <Route path="master/bom-upload" element={<RequirePermission permission="master:write"><BOMUploadPage /></RequirePermission>} />

          {/* Inventory */}
          <Route path="inventory/balances" element={<RequirePermission permission="inventory:read"><InventoryBalancesPage /></RequirePermission>} />
          <Route path="inventory/upload" element={<RequirePermission permission="inventory:upload"><InventoryUploadPage /></RequirePermission>} />
          <Route path="inventory/eod-count" element={<RequirePermission permission="inventory:adjust"><EODCountPage /></RequirePermission>} />
          <Route path="inventory/transactions" element={<RequirePermission permission="inventory:read"><TransactionHistoryPage /></RequirePermission>} />
          <Route path="inventory/variance" element={<RequirePermission permission="inventory:read"><VarianceReportPage /></RequirePermission>} />

          {/* ODS */}
          <Route path="ods/new-request" element={<RequirePermission permission="requests:create"><NewRequestPage /></RequirePermission>} />
          <Route path="ods/requests" element={<RequirePermission permission="requests:read"><ODSRequestsPage /></RequirePermission>} />

          {/* RMPM */}
          <Route path="rmpm/requests" element={<RequirePermission permission="requests:approve"><RMPMRequestsPage /></RequirePermission>} />
          <Route path="rmpm/requests/:id" element={<RequirePermission permission="requests:approve"><RMPMRequestDetailPage /></RequirePermission>} />

          {/* Reports */}
          <Route path="reports/inventory" element={<RequirePermission permission="reports:read"><ReportsInventoryPage /></RequirePermission>} />
          <Route path="reports/requests" element={<RequirePermission permission="reports:read"><ReportsRequestsPage /></RequirePermission>} />
          <Route path="reports/transactions" element={<RequirePermission permission="reports:read"><ReportsTransactionsPage /></RequirePermission>} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
