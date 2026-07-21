import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { tokenStorage } from '@/api/client'
import { authApi } from '@/api/auth'
import type { UserOut } from '@/types/api'

interface AuthContextType {
  user: UserOut | null
  permissions: string[]
  isLoading: boolean
  isAuthenticated: boolean
  mustChangePassword: boolean
  login: (identifier: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasPermission: (permission: string) => boolean
  clearMustChangePassword: () => void
  refetchUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })
  const [permissions, setPermissions] = useState<string[]>(() => {
    const stored = localStorage.getItem('permissions')
    return stored ? JSON.parse(stored) : []
  })
  const [isLoading, setIsLoading] = useState(true)
  const [mustChangePassword, setMustChangePassword] = useState(false)

  // Validate session on mount
  useEffect(() => {
    const validateSession = async () => {
      const token = tokenStorage.getAccess()
      if (!token) {
        setIsLoading(false)
        return
      }
      try {
        const resp = await authApi.me()
        const u = resp.data
        setUser(u)
        setPermissions(u.permissions)
        setMustChangePassword(u.must_change_password ?? false)
        localStorage.setItem('user', JSON.stringify(u))
        localStorage.setItem('permissions', JSON.stringify(u.permissions))
      } catch {
        tokenStorage.clear()
        setUser(null)
        setPermissions([])
        setMustChangePassword(false)
      } finally {
        setIsLoading(false)
      }
    }
    validateSession()
  }, [])

  const refetchUser = useCallback(async () => {
    const token = tokenStorage.getAccess()
    if (!token) return
    try {
      const resp = await authApi.me()
      const u = resp.data
      setUser(u)
      setPermissions(u.permissions)
      setMustChangePassword(u.must_change_password ?? false)
      localStorage.setItem('user', JSON.stringify(u))
      localStorage.setItem('permissions', JSON.stringify(u.permissions))
    } catch {
      // do nothing
    }
  }, [])

  const login = useCallback(async (identifier: string, password: string) => {
    const resp = await authApi.login({ identifier, password })
    const { access_token, refresh_token, permissions: perms } = resp.data
    tokenStorage.setTokens(access_token, refresh_token)

    // Fetch full profile
    const meResp = await authApi.me()
    const u = meResp.data
    setUser(u)
    setPermissions(perms)
    setMustChangePassword(u.must_change_password ?? false)
    localStorage.setItem('user', JSON.stringify(u))
    localStorage.setItem('permissions', JSON.stringify(perms))
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = tokenStorage.getRefresh()
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken)
      } catch {
        // Ignore logout errors
      }
    }
    tokenStorage.clear()
    setUser(null)
    setPermissions([])
    setMustChangePassword(false)
  }, [])

  const hasPermission = useCallback(
    (permission: string) => permissions.includes(permission),
    [permissions]
  )

  const clearMustChangePassword = useCallback(() => {
    setMustChangePassword(false)
    if (user) {
      const updated = { ...user, must_change_password: false }
      setUser(updated)
      localStorage.setItem('user', JSON.stringify(updated))
    }
  }, [user])

  return (
    <AuthContext.Provider
      value={{
        user,
        permissions,
        isLoading,
        isAuthenticated: !!user,
        mustChangePassword,
        login,
        logout,
        hasPermission,
        clearMustChangePassword,
        refetchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
