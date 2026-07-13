
import { useAuth } from '@/contexts/AuthContext'

interface RequirePermissionProps {
  children: React.ReactNode
  permission: string
}

export function RequirePermission({ children, permission }: RequirePermissionProps) {
  const { hasPermission } = useAuth()

  if (!hasPermission(permission)) {
    return (
      <div className="flex h-screen flex-col items-center justify-center p-4 text-center">
        <h1 className="mb-4 text-4xl font-bold text-red-600">403</h1>
        <h2 className="mb-2 text-2xl font-semibold">Unauthorized Access</h2>
        <p className="text-muted-foreground">
          You do not have the required permission ({permission}) to view this page.
        </p>
      </div>
    )
  }

  return <>{children}</>
}
