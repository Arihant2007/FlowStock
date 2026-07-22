import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useLocation, Outlet, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import { Breadcrumb } from '@/components/enterprise/Breadcrumb'
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
  ChevronDown,
  Layers,
  TrendingUp,
  Upload,
  Scale,
  History,
  User,
  ChevronsLeft,
  ChevronsRight,

} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
      { label: 'Material Upload', href: '/master/material-upload', icon: Upload, permission: 'master:write' },
      { label: 'SKUs', href: '/master/skus', icon: Layers },
      { label: 'BOM Upload', href: '/master/bom-upload', icon: Upload, permission: 'master:write' },
      { label: 'Import History', href: '/master/boms', icon: History },
    ],
  },
  {
    label: 'Inventory',
    icon: TrendingUp,
    permission: 'inventory:read',
    children: [
      { label: 'Opening Balance', href: '/inventory/upload', icon: Upload, permission: 'inventory:upload' },
      { label: 'Stock Ledger', href: '/inventory/balances', icon: Scale },
      { label: 'Variance Report', href: '/inventory/variance', icon: Scale },
    ],
  },
  {
    label: 'ODS',
    icon: BookOpen,
    permission: 'requests:create',
    children: [
      { label: 'Upload Requests', href: '/ods/upload', icon: Upload },
      { label: 'New Request', href: '/ods/new-request', icon: ClipboardList },
      { label: 'My Requests', href: '/ods/requests', icon: BookOpen },
    ],
  },
  {
    label: 'RMPM',
    icon: CheckSquare,
    permission: 'requests:approve',
    children: [
      { label: 'Pending Approvals', href: '/rmpm/requests', icon: ClipboardList },
      { label: 'Approved Requests', href: '/rmpm/requests?status=approved', icon: CheckSquare },
    ],
  },
  { label: 'Reports', href: '/reports/inventory', icon: BarChart3, permission: 'reports:read' },

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
    const active =
      location.pathname === item.href ||
      (item.href !== '/dashboard' && location.pathname.startsWith(item.href))
    return (
      <Link
        to={item.href}
        title={collapsed ? item.label : undefined}
        className={cn(
          'relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-all duration-150',
          active
            ? 'bg-[#2563EB] text-white font-bold shadow-sm'
            : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
        )}
      >
        <item.icon className={cn('h-4.5 w-4.5 shrink-0', active ? 'text-white' : 'text-slate-500')} />
        <AnimatePresence>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              className="overflow-hidden whitespace-nowrap"
            >
              {item.label}
            </motion.span>
          )}
        </AnimatePresence>
      </Link>
    )
  }

  if (item.children) {
    const isActiveChild = item.children.some((c) => location.pathname.startsWith(c.href))
    return (
      <div className="space-y-1">
        <button
          onClick={() => setOpen(!open)}
          title={collapsed ? item.label : undefined}
          className={cn(
            'flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-colors',
            isActiveChild && !collapsed
              ? 'text-[#2563EB] font-bold bg-blue-50/70'
              : 'text-slate-600 hover:bg-slate-100/80 hover:text-slate-900'
          )}
        >
          <item.icon className={cn('h-4.5 w-4.5 shrink-0', isActiveChild ? 'text-[#2563EB]' : 'text-slate-500')} />
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                className="flex flex-1 items-center justify-between overflow-hidden whitespace-nowrap"
              >
                <span>{item.label}</span>
                <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
                  <ChevronDown className="h-3.5 w-3.5 opacity-50" />
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </button>
        <AnimatePresence>
          {open && !collapsed && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className="overflow-hidden"
            >
              <div className="ml-5 mt-1 space-y-1 border-l-2 border-slate-200/80 pl-3">
                {item.children.map((child) => {
                  if (child.permission && !hasPermission(child.permission)) return null
                  const active = location.pathname === child.href
                  return (
                    <Link
                      key={child.href}
                      to={child.href}
                      className={cn(
                        'flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors',
                        active
                          ? 'bg-[#2563EB] text-white font-semibold shadow-xs'
                          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                      )}
                    >
                      <child.icon className={cn('h-3.5 w-3.5 shrink-0', active ? 'text-white' : 'opacity-70')} />
                      <span className="truncate">{child.label}</span>
                    </Link>
                  )
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  return null
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Resizable Sidebar State (70px min to 360px max, default 260px)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('stockflow_sidebar_width')
    return saved ? Math.min(Math.max(parseInt(saved, 10), 70), 360) : 260
  })

  const [isDragging, setIsDragging] = useState(false)
  const sidebarRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    localStorage.setItem('stockflow_sidebar_width', sidebarWidth.toString())
  }, [sidebarWidth])

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return
      const newWidth = e.clientX
      const clampedWidth = Math.min(Math.max(newWidth, 70), 360)
      setSidebarWidth(clampedWidth)
    },
    [isDragging]
  )

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    } else {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  const handleDoubleClickReset = () => {
    setSidebarWidth(260)
    toast.info('Sidebar width reset to default (260px)')
  }

  const isCollapsed = sidebarWidth <= 80

  const handleLogout = async () => {
    await logout()
    toast.success('Logged out successfully.')
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F5F7FA] font-sans text-slate-900 selection:bg-[#2563EB] selection:text-white">
      {/* Resizable Enterprise Sidebar (#FCFCFD Surface) */}
      <aside
        ref={sidebarRef}
        style={{ width: `${sidebarWidth}px` }}
        className="relative flex flex-col border-r border-[#E2E8F0] bg-[#FCFCFD] text-slate-900 z-20 shadow-[1px_0_10px_rgba(0,0,0,0.02)] transition-none select-none shrink-0"
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center px-4 border-b border-[#E2E8F0] bg-white">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 text-white shadow-sm">
              <Layers className="h-5 w-5" />
            </div>
            <AnimatePresence>
              {!isCollapsed && (
                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="flex flex-col whitespace-nowrap"
                >
                  <span className="text-base font-bold tracking-tight text-slate-900 leading-none">
                    StockFlow
                  </span>
                  <span className="text-[10px] font-bold text-amber-700 uppercase tracking-wider mt-1">
                    Enterprise ERP
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Navigation Section */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-1.5 scrollbar-thin">
          {NAV_ITEMS.map((item) => (
            <NavSection key={item.label} item={item} collapsed={isCollapsed} />
          ))}
        </nav>

        {/* Quick Toggle Button at Bottom */}
        <div className="p-3 border-t border-[#E2E8F0] bg-white/50">
          <button
            onClick={() => setSidebarWidth(isCollapsed ? 260 : 70)}
            title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            className="flex w-full items-center justify-center gap-2 rounded-xl p-2 text-xs font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            {isCollapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
            {!isCollapsed && <span>Collapse Menu</span>}
          </button>
        </div>

        {/* Draggable Resize Handle (4-6px) on Right Edge */}
        <div
          onMouseDown={() => setIsDragging(true)}
          onDoubleClick={handleDoubleClickReset}
          title="Drag to resize sidebar · Double-click to reset (260px)"
          className={cn(
            'absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize z-30 transition-colors duration-150 hover:bg-[#2563EB]/40',
            isDragging && 'bg-[#2563EB] w-2'
          )}
        />
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden relative min-w-0">
        {/* SadaxCart Style Top Navigation Header */}
        <header className="flex h-16 items-center justify-between border-b border-[#E2E8F0] bg-white px-6 shadow-[0_2px_8px_rgba(0,0,0,0.02)] z-10 shrink-0">
          <div className="flex items-center">
            <Breadcrumb />
          </div>

          {/* Right: User Menu */}
          <div className="flex items-center gap-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  className="relative flex items-center gap-3 rounded-full pl-2 pr-3 hover:bg-slate-50"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#2563EB] text-white font-bold text-xs shadow-sm">
                    {(user?.full_name || user?.username || 'A')[0].toUpperCase()}
                  </div>
                  <div className="flex flex-col items-start hidden sm:flex text-left">
                    <span className="text-xs font-bold text-slate-900 leading-none">
                      {user?.full_name || user?.username}
                    </span>
                    <span className="text-[10px] font-semibold text-slate-500 mt-1 uppercase tracking-wider">
                      {user?.role_name || 'System Administrator'}
                    </span>
                  </div>
                  <ChevronDown className="h-3.5 w-3.5 text-slate-400 ml-1 hidden sm:block" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 rounded-2xl shadow-lg border-slate-100 p-1">
                <DropdownMenuLabel className="text-xs text-slate-500 font-normal px-3 py-2">
                  Signed in as <strong className="text-slate-900">{user?.username}</strong>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => navigate('/settings')}
                  className="cursor-pointer rounded-xl text-xs py-2 px-3"
                >
                  <User className="mr-2 h-4 w-4 text-slate-400" />
                  <span>Profile Settings</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={handleLogout}
                  className="cursor-pointer text-red-600 focus:bg-red-50 focus:text-red-700 rounded-xl text-xs py-2 px-3"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>Log out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Main Content View Container */}
        <main className="flex-1 overflow-y-auto bg-[#F5F7FA] p-6 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
