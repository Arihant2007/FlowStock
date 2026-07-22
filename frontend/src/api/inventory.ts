import client from './client'
import type {
  ApiResponse,
  InventoryBalance,
  InventoryTransactionOut,
  OpeningBalanceUploadPreview,
} from '@/types/api'

export const inventoryApi = {
  previewUpload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post<ApiResponse<OpeningBalanceUploadPreview>>(
      '/inventory/upload/preview',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  commitUpload: async (file: File, ignoreWarnings = false) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post<ApiResponse<{ adjustments_created: number; snapshots_upserted: number }>>(
      `/inventory/upload/commit?ignore_warnings=${ignoreWarnings}`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  submitEODCount: async (payload: {
    count_date: string
    items: { material_public_id: string; warehouse_public_id: string; actual_quantity: string }[]
  }) => {
    const { data } = await client.post<ApiResponse<{ count_date: string; adjustments: unknown[] }>>(
      '/inventory/eod-count',
      payload
    )
    return data
  },

  getBalances: async (page = 1, pageSize = 50) => {
    const { data } = await client.get<ApiResponse<InventoryBalance[]>>('/inventory/balances', {
      params: { page, page_size: pageSize },
    })
    return data
  },

  getTransactions: async (params: {
    page?: number
    page_size?: number
    transaction_type?: string
    material_public_id?: string
    warehouse_public_id?: string
  } = {}) => {
    const { data } = await client.get<ApiResponse<InventoryTransactionOut[]>>(
      '/inventory/transactions',
      { params: { page: 1, page_size: 50, ...params } }
    )
    return data
  },

  getVarianceReport: async (params: {
    page?: number
    page_size?: number
    warehouse_public_id?: string
    snapshot_date?: string
  } = {}) => {
    const { data } = await client.get('/inventory/variance-report', {
      params: { page: 1, page_size: 50, ...params },
    })
    return data
  },

  exportVarianceReport: async (params: {
    format?: 'excel' | 'csv'
    warehouse_public_id?: string
    snapshot_date?: string
  } = {}) => {
    const res = await client.get('/inventory/variance-report/export', {
      params,
      responseType: 'blob',
    })
    return res
  },

  downloadTemplate: async () => {
    const res = await client.get('/inventory/upload/template', {
      responseType: 'blob',
    })
    return res
  },
}
