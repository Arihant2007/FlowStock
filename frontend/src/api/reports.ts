import client from './client'

export const reportsApi = {
  // Ledger
  getLedger: (params: Record<string, any>) =>
    client.get('/reports/inventory', { params }).then((res) => res.data),
  exportLedger: (params: Record<string, any>) =>
    client.get('/reports/inventory/export', { params, responseType: 'blob' }),

  // Variance
  getVariance: (params: Record<string, any>) =>
    client.get('/reports/variance', { params }).then((res) => res.data),
  exportVariance: (params: Record<string, any>) =>
    client.get('/reports/variance/export', { params, responseType: 'blob' }),

  // Requests
  getRequests: (params: Record<string, any>) =>
    client.get('/reports/requests', { params }).then((res) => res.data),
  exportRequests: (params: Record<string, any>) =>
    client.get('/reports/requests/export', { params, responseType: 'blob' }),

  // Production
  getProduction: (params: Record<string, any>) =>
    client.get('/reports/production', { params }).then((res) => res.data),
  exportProduction: (params: Record<string, any>) =>
    client.get('/reports/production/export', { params, responseType: 'blob' }),
}

// Utility to handle downloading the blob
export const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}
