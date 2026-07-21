import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { authApi } from '@/api/auth'
import { toast } from 'sonner'
import { KeyRound, Eye, EyeOff, AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ForceChangePasswordPage() {
  const { user, logout, clearMustChangePassword, refetchUser } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [username, setUsername] = useState(user?.username || '')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error('Please fill in all fields.')
      return
    }
    if (newPassword.length < 8) {
      toast.error('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match.')
      return
    }
    if (currentPassword === newPassword) {
      toast.error('New password must be different from the temporary password.')
      return
    }

    setIsSubmitting(true)
    try {
      if (username.trim() && username !== user?.username) {
        await authApi.updateProfile({ username: username.trim() })
      }
      await authApi.changePassword({ current_password: currentPassword, new_password: newPassword })
      clearMustChangePassword()
      await refetchUser()
      toast.success('Setup completed successfully. Welcome!')
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? 'Failed to change password. Check your current password.'
      toast.error(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-[#F5F7FA] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="bg-white rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.06)] border border-[#E2E8F0] overflow-hidden">
          {/* Warning Banner */}
          <div className="bg-amber-50 border-b border-amber-100 px-6 py-4 flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-100">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xs font-bold text-amber-800">Password Change Required</p>
              <p className="text-xs text-amber-700 mt-0.5">
                Your password was reset by an administrator. You must set a new password before accessing the application.
              </p>
            </div>
          </div>

          {/* Form */}
          <div className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#2563EB]/10">
                <KeyRound className="h-5 w-5 text-[#2563EB]" />
              </div>
              <div>
                <h1 className="text-base font-bold text-slate-900">Set New Password</h1>
                <p className="text-xs text-slate-500">Signed in as <strong>{user?.username}</strong></p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Change Username <span className="text-slate-400 font-normal normal-case">(Optional)</span>
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={user?.username}
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                />
              </div>

              {/* Current (temp) password */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Temporary Password
                </label>
                <div className="relative">
                  <input
                    type={showCurrent ? 'text' : 'password'}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter the temporary password"
                    className="w-full rounded-xl border border-slate-200 pr-10 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrent(!showCurrent)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* New password */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  New Password
                </label>
                <div className="relative">
                  <input
                    type={showNew ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min. 8 characters"
                    className="w-full rounded-xl border border-slate-200 pr-10 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNew(!showNew)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Confirm */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                  Confirm New Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat your new password"
                    className="w-full rounded-xl border border-slate-200 pr-10 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="pt-2 space-y-2">
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full rounded-xl bg-[#2563EB] hover:bg-blue-700 text-white font-bold text-sm h-10 shadow-sm flex items-center justify-center gap-2"
                >
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  {isSubmitting ? 'Changing Password…' : 'Set New Password'}
                </Button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full text-xs text-slate-400 hover:text-slate-600 py-1.5 transition-colors"
                >
                  Sign out instead
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
