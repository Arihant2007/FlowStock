import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { authApi } from '@/api/auth'
import { PageHeader } from '@/components/enterprise/PageHeader'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { User, Shield, Key, Building2, CheckCircle2, BadgeCheck } from 'lucide-react'

export function SettingsPage() {
  const { user, refetchUser } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false)

  const [username, setUsername] = useState(user?.username || '')
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false)

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error('Please fill in all password fields.')
      return
    }
    if (newPassword.length < 8) {
      toast.error('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('New password and confirm password do not match.')
      return
    }
    setIsUpdatingPassword(true)
    try {
      await authApi.changePassword({ current_password: currentPassword, new_password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Password updated successfully.')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? 'Failed to update password. Check your current password.'
      toast.error(msg)
    } finally {
      setIsUpdatingPassword(false)
    }
  }

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim()) {
      toast.error('Username cannot be empty.')
      return
    }
    if (!fullName.trim()) {
      toast.error('Full Name cannot be empty.')
      return
    }
    if (username === user?.username && fullName === user?.full_name) {
      toast.info('No changes made.')
      return
    }

    setIsUpdatingProfile(true)
    try {
      await authApi.updateProfile({ username, full_name: fullName })
      toast.success('Profile updated successfully.')
      refetchUser()
    } catch (err: any) {
      console.error(err)
      const msg = err.response?.data?.message || err.response?.data?.detail || 'Failed to update profile.'
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setIsUpdatingProfile(false)
    }
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Profile & Settings"
        description="Manage your enterprise account details, role permissions, and security settings."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* User Card */}
        <div className="md:col-span-1 rounded-2xl bg-white p-6 shadow-[0_2px_12px_rgba(0,0,0,0.03)] border border-[#E2E8F0] flex flex-col items-center text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-[#2563EB] text-white text-2xl font-bold shadow-md mb-4">
            {(user?.full_name || user?.username || 'A')[0].toUpperCase()}
          </div>
          <h2 className="text-xl font-bold text-slate-900">{user?.full_name || user?.username}</h2>
          <p className="text-xs font-semibold text-slate-500 mt-0.5">{user?.username}</p>

          <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 border border-blue-200/60">
            <BadgeCheck className="h-3.5 w-3.5" />
            <span>{user?.role_name || 'System Administrator'}</span>
          </div>

          <div className="w-full mt-6 pt-6 border-t border-slate-100 space-y-3 text-left">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-500">Account Status</span>
              <span className="inline-flex items-center text-emerald-600 font-bold gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Active
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-500">Authentication</span>
              <span className="font-bold text-slate-700">Enterprise SSO / Local</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-500">System Permissions</span>
              <span className="font-bold text-blue-600">{user?.permissions?.length || 12} Granted</span>
            </div>
          </div>
        </div>

        {/* Security & Settings Content */}
        <div className="md:col-span-2 space-y-6">
          {/* Account Details Card */}
          <div className="rounded-2xl bg-white p-6 shadow-[0_2px_12px_rgba(0,0,0,0.03)] border border-[#E2E8F0]">
            <div className="flex items-center gap-2 mb-4">
              <User className="h-5 w-5 text-[#2563EB]" />
              <h3 className="text-base font-bold text-slate-900">Account Profile</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:border-[#2563EB] focus:ring-1 focus:ring-[#2563EB] transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Assigned Unit / Warehouse
                </label>
                <div className="flex items-center gap-2 rounded-xl bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-800">
                  <Building2 className="h-4 w-4 text-slate-400 shrink-0" />
                  <span>Central ITC Warehouses (ODS & RMPM)</span>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Role Authority
                </label>
                <div className="flex items-center gap-2 rounded-xl bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-800">
                  <Shield className="h-4 w-4 text-blue-600 shrink-0" />
                  <span>{user?.role_name || 'System Administrator'}</span>
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button
                onClick={handleProfileUpdate}
                disabled={isUpdatingProfile || (username === user?.username && fullName === user?.full_name)}
                className="rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-semibold text-xs h-9 px-5 shadow-sm"
              >
                {isUpdatingProfile ? 'Saving...' : 'Save Profile Changes'}
              </Button>
            </div>
          </div>

          {/* Change Password Card */}
          <div className="rounded-2xl bg-white p-6 shadow-[0_2px_12px_rgba(0,0,0,0.03)] border border-[#E2E8F0]">
            <div className="flex items-center gap-2 mb-4">
              <Key className="h-5 w-5 text-amber-600" />
              <h3 className="text-base font-bold text-slate-900">Security & Credentials</h3>
            </div>
            <form onSubmit={handlePasswordUpdate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Current Password
                </label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="Enter current password"
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    New Password
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Enter new password"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-medium text-slate-800 transition-all focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                  />
                </div>
              </div>
              <div className="pt-2 flex justify-end">
                <Button
                  type="submit"
                  disabled={isUpdatingPassword}
                  className="rounded-xl bg-[#2563EB] hover:bg-blue-700 text-white font-semibold text-xs h-9 px-5 shadow-sm"
                >
                  {isUpdatingPassword ? 'Updating...' : 'Update Password'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
