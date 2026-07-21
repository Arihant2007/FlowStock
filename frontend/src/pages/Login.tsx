import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { getErrorMessage } from '@/lib/utils'
import { User, Lock, Eye, EyeOff } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const loginSchema = z.object({
  identifier: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof loginSchema>

export function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)

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

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  }

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: {
      y: 0,
      opacity: 1,
      transition: { type: 'spring' as const, stiffness: 100, damping: 15 },
    },
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-black overflow-hidden font-sans selection:bg-[#2563EB] selection:text-white">
      {/* Background artwork shifted slightly to the right so brightest streaks don't intersect the form */}
      <img
        src="/images/itc-login-bg.png"
        alt="ITC Abstract Background"
        className="absolute inset-0 w-full h-full object-cover object-[75%_center] opacity-90"
      />

      {/* Abstract Animated Glow overlay */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div
          animate={{
            scale: [1, 1.05, 1],
            opacity: [0.25, 0.45, 0.25],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-1/2 right-[-5%] w-[55%] h-[100%] -translate-y-1/2 bg-gradient-to-l from-[#ff4d00]/30 via-[#aa0000]/15 to-transparent rounded-full blur-[140px] mix-blend-screen"
        />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10 mix-blend-overlay"></div>
      </div>

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="relative z-10 w-full max-w-[480px] px-6 sm:px-8 py-12 flex flex-col items-center"
      >
        {/* Official ITC Logo (Flat Pure White Monochrome, No Glow) */}
        <motion.div variants={itemVariants} className="mb-10 text-center flex flex-col items-center">
          <img
            src="/images/itc-logo-white.png"
            alt="ITC Limited Logo"
            className="h-[74px] w-auto object-contain opacity-95"
          />
        </motion.div>

        {/* Heading */}
        <motion.div variants={itemVariants} className="mb-12 w-full text-center">
          <h1
            className="text-4xl sm:text-[44px] text-white tracking-tight leading-tight"
            style={{ fontFamily: '"Playfair Display", "Cormorant Garamond", serif' }}
          >
            Welcome Back !
          </h1>
        </motion.div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="w-full space-y-6">
          <AnimatePresence>
            {serverError && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="rounded-xl bg-red-500/15 border border-red-500/30 px-4 py-3 text-sm text-red-100 text-center backdrop-blur-md"
              >
                {serverError}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Username Field */}
          <motion.div variants={itemVariants} className="space-y-2">
            <label htmlFor="identifier" className="block text-xs font-semibold text-slate-200 uppercase tracking-wider ml-1">
              Username / Employee ID
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <User className="h-5 w-5 text-slate-400 transition-colors duration-300 group-focus-within:text-[#2563EB]" />
              </div>
              <input
                id="identifier"
                type="text"
                placeholder="Enter your Username or Employee ID"
                className="w-full pl-11 pr-4 h-[54px] bg-slate-900/60 backdrop-blur-md border border-white/30 rounded-2xl text-white placeholder:text-slate-400 text-sm font-medium transition-all duration-300 focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/40 focus:shadow-[0_0_15px_rgba(37,99,235,0.3)] hover:bg-slate-900/80 hover:border-white/40"
                {...register('identifier')}
              />
            </div>
            {errors.identifier && (
              <p className="text-xs font-medium text-red-400 ml-1 mt-1">{errors.identifier.message}</p>
            )}
          </motion.div>

          {/* Password Field */}
          <motion.div variants={itemVariants} className="space-y-2">
            <label htmlFor="password" className="block text-xs font-semibold text-slate-200 uppercase tracking-wider ml-1">
              Password
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-slate-400 transition-colors duration-300 group-focus-within:text-[#2563EB]" />
              </div>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                className="w-full pl-11 pr-12 h-[54px] bg-slate-900/60 backdrop-blur-md border border-white/30 rounded-2xl text-white placeholder:text-slate-400 text-sm font-medium transition-all duration-300 focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/40 focus:shadow-[0_0_15px_rgba(37,99,235,0.3)] hover:bg-slate-900/80 hover:border-white/40"
                {...register('password')}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-white transition-colors focus:outline-none"
              >
                {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {errors.password && (
              <p className="text-xs font-medium text-red-400 ml-1 mt-1">{errors.password.message}</p>
            )}
          </motion.div>

          {/* Sign In Button with ITC Blue hover state and loading animation */}
          <motion.div variants={itemVariants} className="pt-3">
            <motion.button
              whileHover={{ scale: 1.015 }}
              whileTap={{ scale: 0.985 }}
              type="submit"
              disabled={isSubmitting}
              className="relative w-full h-[54px] rounded-2xl bg-[#0F4C81] hover:bg-[#2563EB] text-white font-semibold text-sm tracking-wide shadow-lg shadow-blue-900/30 transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {isSubmitting ? (
                <div className="flex items-center gap-2">
                  <div className="h-5 w-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Authenticating...</span>
                </div>
              ) : (
                <span>Sign In</span>
              )}
            </motion.button>
          </motion.div>
        </form>
      </motion.div>
    </div>
  )
}
