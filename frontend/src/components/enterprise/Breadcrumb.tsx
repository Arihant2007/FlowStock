import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'

const ROUTE_NAME_MAP: Record<string, string> = {
  dashboard: 'Dashboard',
  master: 'Master Data',
  materials: 'Materials',
  warehouses: 'Warehouses',
  skus: 'SKUs',
  boms: 'Import History',
  'material-upload': 'Material Upload',
  'bom-upload': 'BOM Upload',
  inventory: 'Inventory',
  upload: 'Opening Balance',
  balances: 'Stock Ledger',
  variance: 'Variance Report',
  ods: 'ODS',
  'new-request': 'New Request',
  requests: 'Requests',
  rmpm: 'RMPM',
  reports: 'Reports',
  settings: 'Administration',
}

export function Breadcrumb() {
  const location = useLocation()
  const pathnames = location.pathname.split('/').filter((x) => x)

  return (
    <nav className="flex items-center gap-1.5 text-xs font-medium text-slate-500 mb-2">
      <Link
        to="/dashboard"
        className="flex items-center gap-1 hover:text-slate-900 transition-colors"
      >
        <Home className="h-3.5 w-3.5" />
      </Link>
      {pathnames.length > 0 && <ChevronRight className="h-3.5 w-3.5 text-slate-300 shrink-0" />}

      {pathnames.map((value, index) => {
        const to = `/${pathnames.slice(0, index + 1).join('/')}`
        const isLast = index === pathnames.length - 1
        const displayName = ROUTE_NAME_MAP[value] || value.replace(/-/g, ' ')

        return (
          <div key={to} className="flex items-center gap-1.5">
            {isLast ? (
              <span className="font-semibold text-slate-900 capitalize">{displayName}</span>
            ) : (
              <Link to={to} className="hover:text-slate-900 transition-colors capitalize">
                {displayName}
              </Link>
            )}
            {!isLast && <ChevronRight className="h-3.5 w-3.5 text-slate-300 shrink-0" />}
          </div>
        )
      })}
    </nav>
  )
}
