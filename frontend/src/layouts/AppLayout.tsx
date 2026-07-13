import { Link, useLocation, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Database,
  Package,
  Warehouse,
  BookOpen,
  ClipboardList,
  CheckSquare,
  BarChart3,
  LogOut,
  Menu,
  X,
  ChevronDown,
  ChevronRight,
  Factory,
  Layers,
  TrendingUp,
  Upload,
  Scale,
  History,
} from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface NavItem {
  label: string
  href?: string
  icon: React.ElementType
  permission?: string
  children?: { label: string; href: string; icon: React.ElementType; permission?: string }[]
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  {
    label: 'Master Data',
    icon: Database,
    permission: 'master:read',
    children: [
      { label: 'Warehouses', href: '/master/warehouses', icon: Warehouse },
      { label: 'Materials', href: '/master/materials', icon: Package },
      { label: 'SKUs', href: '/master/skus', icon: Layers },
      { label: 'BOM Upload', href: '/master/bom-upload', icon: Upload },
    ],
  },
  {
    label: 'Inventory',
    icon: TrendingUp,
    permission: 'inventory:read',
    children: [
      { label: 'Balances', href: '/inventory/balances', icon: Scale },
      { label: 'Upload Snapshot', href: '/inventory/upload', icon: Upload, permission: 'inventory:upload' },
      { label: 'EOD Count', href: '/inventory/eod-count', icon: ClipboardList, permission: 'inventory:adjust' },
      { label: 'Transactions', href: '/inventory/transactions', icon: History },
    ],
  },
  {
    label: 'ODS',
    icon: Factory,
    permission: 'requests:create',
    children: [
      { label: 'New Request', href: '/ods/new-request', icon: ClipboardList },
      { label: 'My Requests', href: '/ods/requests', icon: BookOpen },
    ],
  },
  {
    label: 'RMPM',
    icon: CheckSquare,
    permission: 'requests:approve',
    children: [
      { label: 'Pending Requests', href: '/rmpm/requests', icon: ClipboardList },
    ],
  },
  {
    label: 'Reports',
    icon: BarChart3,
    permission: 'reports:read',
    children: [
      { label: 'Daily Inventory', href: '/reports/inventory', icon: TrendingUp },
      { label: 'Material Requests', href: '/reports/requests', icon: ClipboardList },
      { label: 'Transactions', href: '/reports/transactions', icon: History },
    ],
  },
]

function NavSection({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const location = useLocation()
  const { hasPermission } = useAuth()
  const [open, setOpen] = useState(() => {
    if (item.children) {
      return item.children.some((c) => location.pathname.startsWith(c.href))
    }
    return false
  })

  if (item.permission && !hasPermission(item.permission)) return null

  if (item.href) {
    const active = location.pathname === item.href
    return (
      <Link
        to={item.href}
        className={cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          active
            ? 'bg-sidebar-primary text-sidebar-primary-foreground'
            : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
        )}
      >
        <item.icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span>{item.label}</span>}
      </Link>
    )
  }

  if (item.children) {
    return (
      <div>
        <button
          onClick={() => setOpen(!open)}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
        >
          <item.icon className="h-4 w-4 shrink-0" />
          {!collapsed && (
            <>
              <span className="flex-1 text-left">{item.label}</span>
              {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </>
          )}
        </button>
        {open && !collapsed && (
          <div className="ml-4 mt-1 space-y-0.5 border-l border-sidebar-border pl-3">
            {item.children.map((child) => {
              if (child.permission && !hasPermission(child.permission)) return null
              const active = location.pathname === child.href
              return (
                <Link
                  key={child.href}
                  to={child.href}
                  className={cn(
                    'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors',
                    active
                      ? 'bg-sidebar-primary/10 text-sidebar-primary font-medium'
                      : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                  )}
                >
                  <child.icon className="h-3.5 w-3.5" />
                  {child.label}
                </Link>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return null
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const handleLogout = async () => {
    await logout()
    toast.success('Logged out successfully.')
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          'flex flex-col transition-all duration-300 ease-in-out bg-[hsl(var(--sidebar-background))]',
          sidebarOpen ? 'w-64' : 'w-16'
        )}
      >
        {/* Brand */}
        <div className="flex h-14 items-center justify-between px-3 border-b border-sidebar-border">
          {sidebarOpen && (
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="h-7 w-7 rounded-lg bg-sidebar-primary flex items-center justify-center shrink-0">
                <Factory className="h-4 w-4 text-white" />
              </div>
              <span className="font-semibold text-sidebar-foreground text-sm whitespace-nowrap">
                ITC WMS
              </span>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="text-sidebar-foreground hover:bg-sidebar-accent h-8 w-8 shrink-0"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <NavSection key={item.label} item={item} collapsed={!sidebarOpen} />
          ))}
        </nav>

        {/* User footer */}
        <div className="border-t border-sidebar-border p-3">
          {sidebarOpen ? (
            <div className="flex items-center justify-between">
              <div className="overflow-hidden">
                <p className="text-xs font-medium text-sidebar-foreground truncate">{user?.full_name}</p>
                <p className="text-xs text-sidebar-foreground/50 truncate">{user?.role_name}</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground h-8 w-8 shrink-0"
                onClick={handleLogout}
                title="Log out"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              className="text-sidebar-foreground/70 hover:bg-sidebar-accent h-8 w-8"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 items-center border-b bg-background px-6 gap-4">
          <div className="flex-1" />
          <div className="text-sm text-muted-foreground">
            {user?.username && (
              <span>
                Signed in as <span className="font-medium text-foreground">{user.username}</span>
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
