import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(d)
  } catch {
    return dateStr
  }
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return dateStr
  }
}

export function formatQty(qty: string | number | null | undefined, decimals = 4): string {
  if (qty == null || qty === '') return '—'
  const num = typeof qty === 'string' ? parseFloat(qty) : qty
  if (isNaN(num)) return '—'
  return num.toLocaleString('en-IN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })
}

export function getErrorMessage(error: unknown): string {
  if (!error) return 'An unknown error occurred.'
  // Axios error
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const axiosError = error as { response?: { data?: { message?: string; detail?: string } } }
    return (
      axiosError.response?.data?.message ||
      axiosError.response?.data?.detail ||
      'Request failed.'
    )
  }
  if (error instanceof Error) return error.message
  return String(error)
}

export const STATUS_COLORS: Record<string, string> = {
  SUBMITTED: 'bg-blue-100 text-blue-800 border-blue-200',
  RESERVED: 'bg-purple-100 text-purple-800 border-purple-200',
  APPROVED: 'bg-green-100 text-green-800 border-green-200',
  PARTIALLY_APPROVED: 'bg-amber-100 text-amber-800 border-amber-200',
  DISPATCHED: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  RECEIVED: 'bg-teal-100 text-teal-800 border-teal-200',
  CLOSED: 'bg-gray-100 text-gray-700 border-gray-200',
  REJECTED: 'bg-red-100 text-red-800 border-red-200',
}

export const TX_TYPE_COLORS: Record<string, string> = {
  RECEIPT: 'bg-green-100 text-green-800',
  ADJUSTMENT: 'bg-amber-100 text-amber-800',
  RESERVATION: 'bg-purple-100 text-purple-800',
  TRANSFER_IN: 'bg-blue-100 text-blue-800',
  TRANSFER_OUT: 'bg-orange-100 text-orange-800',
  DISPATCH: 'bg-red-100 text-red-800',
}
