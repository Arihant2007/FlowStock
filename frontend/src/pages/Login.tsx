import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getErrorMessage } from '@/lib/utils'
import { Factory, Lock, User } from 'lucide-react'
import { useState } from 'react'

const loginSchema = z.object({
  identifier: z.string().min(3, 'Enter your username or email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

type LoginForm = z.infer<typeof loginSchema>

export function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })

  if (isAuthenticated) return <Navigate to="/dashboard" replace />

  const onSubmit = async (data: LoginForm) => {
    setServerError(null)
    try {
      await login(data.identifier, data.password)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setServerError(getErrorMessage(err))
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      {/* Background decorations */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-blue-500/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-purple-500/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md space-y-6">
        {/* Logo */}
        <div className="text-center">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 shadow-xl shadow-blue-500/30 mb-4">
            <Factory className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">ITC WMS</h1>
          <p className="text-slate-400 text-sm mt-1">Warehouse Management System</p>
        </div>

        <Card className="border-slate-700 bg-slate-800/50 backdrop-blur-sm shadow-2xl">
          <CardHeader className="pb-4">
            <CardTitle className="text-xl text-white">Sign in</CardTitle>
            <CardDescription className="text-slate-400">
              Enter your credentials to access the system
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {serverError && (
                <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                  {serverError}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="identifier" className="text-slate-300">
                  Username or Email
                </Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <Input
                    id="identifier"
                    placeholder="admin"
                    className="pl-9 bg-slate-900/50 border-slate-600 text-white placeholder:text-slate-600 focus-visible:ring-blue-500"
                    {...register('identifier')}
                  />
                </div>
                {errors.identifier && (
                  <p className="text-xs text-red-400">{errors.identifier.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-slate-300">
                  Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    className="pl-9 bg-slate-900/50 border-slate-600 text-white placeholder:text-slate-600 focus-visible:ring-blue-500"
                    {...register('password')}
                  />
                </div>
                {errors.password && (
                  <p className="text-xs text-red-400">{errors.password.message}</p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/20 mt-2"
                isLoading={isSubmitting}
              >
                Sign in
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-slate-600">
          ITC Plant · FMCG Inventory Transfer System v1.0
        </p>
      </div>
    </div>
  )
}
