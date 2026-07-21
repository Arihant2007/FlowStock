import client from './client'
import type {
  ApiResponse,
  WarehouseOut,
  MaterialOut,
  SKUOut,
  SKUOption,
  BOMVersionOut,
  BOMUploadPreview,
  MaterialUploadPreview,
} from '@/types/api'

// ─── Warehouses ───────────────────────────────────────────────────────────────

export const masterApi = {
  // Warehouses
  listWarehouses: async (page = 1, pageSize = 50) => {
    const { data } = await client.get<ApiResponse<WarehouseOut[]>>('/master/warehouses', {
      params: { page, page_size: pageSize },
    })
    return data
  },

  getWarehouse: async (id: string) => {
    const { data } = await client.get<ApiResponse<WarehouseOut>>(`/master/warehouses/${id}`)
    return data
  },

  createWarehouse: async (payload: { name: string; type: string; description: string }) => {
    const { data } = await client.post<ApiResponse<WarehouseOut>>('/master/warehouses', payload)
    return data
  },

  updateWarehouse: async (id: string, payload: { name?: string; description?: string; version: number }) => {
    const { data } = await client.put<ApiResponse<WarehouseOut>>(`/master/warehouses/${id}`, payload)
    return data
  },

  deleteWarehouse: async (id: string) => {
    const { data } = await client.delete<ApiResponse<{}>>(`/master/warehouses/${id}`)
    return data
  },

  // Materials
  listMaterials: async (page = 1, pageSize = 50) => {
    const { data } = await client.get<ApiResponse<MaterialOut[]>>('/master/materials', {
      params: { page, page_size: pageSize },
    })
    return data
  },

  getMaterial: async (id: string) => {
    const { data } = await client.get<ApiResponse<MaterialOut>>(`/master/materials/${id}`)
    return data
  },

  createMaterial: async (payload: {
    code: string
    name: string
    uom: string
    category_public_id: string
    type_public_id: string
    group_public_id?: string
  }) => {
    const { data } = await client.post<ApiResponse<MaterialOut>>('/master/materials', payload)
    return data
  },

  updateMaterial: async (
    id: string,
    payload: { name?: string; uom?: string; version: number }
  ) => {
    const { data } = await client.put<ApiResponse<MaterialOut>>(`/master/materials/${id}`, payload)
    return data
  },

  archiveMaterial: async (id: string) => {
    const { data } = await client.post<ApiResponse<{}>>(`/master/materials/${id}/archive`)
    return data
  },

  downloadMaterialTemplate: async () => {
    const response = await client.get('/master/materials/upload/template', {
      responseType: 'blob',
    })
    return response.data
  },

  previewMaterialUpload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post<ApiResponse<MaterialUploadPreview>>(
      '/master/materials/upload/preview',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  commitMaterialUpload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post<ApiResponse<{ created: number; updated: number; skipped: number }>>(
      '/master/materials/upload/commit',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  extractMaterialsFromBOM: async (file: File | null, sessionId: string | null, onlyUnknown: boolean = true) => {
    const form = new FormData()
    if (file) form.append('file', file)
    if (sessionId) form.append('session_id', sessionId)
    const response = await client.post('/master/materials/extract-from-bom', form, {
      params: { only_unknown: onlyUnknown },
      responseType: 'blob',
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  // SKUs
  listSKUs: async (page = 1, pageSize = 50) => {
    const { data } = await client.get<ApiResponse<SKUOut[]>>('/master/skus', {
      params: { page, page_size: pageSize },
    })
    return data
  },

  /** Lightweight endpoint — returns only public_id/code/name, no pagination. Use for dropdowns. */
  listSKUOptions: async () => {
    const { data } = await client.get<ApiResponse<SKUOption[]>>('/master/skus/options')
    return data
  },

  getSKU: async (id: string) => {
    const { data } = await client.get<ApiResponse<SKUOut>>(`/master/skus/${id}`)
    return data
  },

  createSKU: async (payload: { code: string; name: string; description: string }) => {
    const { data } = await client.post<ApiResponse<SKUOut>>('/master/skus', payload)
    return data
  },

  updateSKU: async (id: string, payload: { name?: string; description?: string; version: number }) => {
    const { data } = await client.put<ApiResponse<SKUOut>>(`/master/skus/${id}`, payload)
    return data
  },

  deleteSKU: async (id: string) => {
    const { data } = await client.delete<ApiResponse<{}>>(`/master/skus/${id}`)
    return data
  },

  // BOM
  getActiveBOM: async (skuId: string) => {
    const { data } = await client.get<ApiResponse<BOMVersionOut>>(`/master/skus/${skuId}/bom`)
    return data
  },

  previewBOMUpload: async (params: { file?: File; sessionId?: string }) => {
    const form = new FormData()
    if (params.file) form.append('file', params.file)
    if (params.sessionId) form.append('session_id', params.sessionId)
    
    const { data } = await client.post<ApiResponse<BOMUploadPreview>>(
      '/master/boms/upload/preview',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  commitBOMUpload: async (sessionId: string) => {
    const form = new FormData()
    form.append('session_id', sessionId)
    const { data } = await client.post<ApiResponse<{
      skus_created: number;
      skus_updated: number;
      bom_versions_created: number;
      items_created: number;
      materials_referenced: number;
      warnings: string[];
      duration_seconds: number;
    }>>(
      '/master/boms/upload/commit',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  cancelBOMUpload: async (sessionId: string) => {
    const { data } = await client.delete<ApiResponse<{}>>(`/master/boms/upload/session/${sessionId}`)
    return data
  },

  getBOMUploadHistory: async () => {
    // Assuming BOMUploadSessionOut type is added to types/api.ts
    const { data } = await client.get<ApiResponse<any[]>>('/master/boms/uploads/history')
    return data
  },

  getDashboardStats: async () => {
    const { data } = await client.get<ApiResponse<{
      total_materials: number;
      total_skus: number;
      total_bom_versions: number;
      total_bom_items: number;
      last_import_at: string | null;
    }>>('/master/dashboard/stats')
    return data
  },
}
