import client from './client'
import type {
  ApiResponse,
  MaterialRequestOut,
  MaterialRequestListItem,
  CreateRequestPayload,
  ApproveRequestPayload,
  RequestPreviewPayload,
  RequestPreviewOut,
} from '@/types/api'

export const requestsApi = {
  listRequests: async (page = 1, pageSize = 20) => {
    const { data } = await client.get<ApiResponse<MaterialRequestListItem[]>>('/requests', {
      params: { page, page_size: pageSize },
    })
    return data
  },

  getRequest: async (id: string) => {
    const { data } = await client.get<ApiResponse<MaterialRequestOut>>(`/requests/${id}`)
    return data
  },

  createRequest: async (payload: CreateRequestPayload) => {
    const { data } = await client.post<ApiResponse<MaterialRequestOut>>('/requests', payload)
    return data
  },

  previewRequest: async (payload: RequestPreviewPayload) => {
    const { data } = await client.post<ApiResponse<RequestPreviewOut>>('/requests/preview', payload)
    return data
  },

  approve: async (id: string, payload: ApproveRequestPayload) => {
    const { data } = await client.put<ApiResponse<{ status: string }>>(`/requests/${id}/approve`, payload)
    return data
  },

  dispatch: async (id: string) => {
    const { data } = await client.post<ApiResponse<{ status: string }>>(`/requests/${id}/dispatch`)
    return data
  },

  receive: async (id: string) => {
    const { data } = await client.post<ApiResponse<{ status: string }>>(`/requests/${id}/receive`)
    return data
  },

  close: async (id: string) => {
    const { data } = await client.post<ApiResponse<{ status: string }>>(`/requests/${id}/close`)
    return data
  },

  reject: async (id: string) => {
    const { data } = await client.post<ApiResponse<{ status: string }>>(`/requests/${id}/reject`)
    return data
  },

  previewUpload: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await client.post<ApiResponse<any>>(
      '/requests/upload/preview',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return data
  },

  commitUpload: async (payload: any) => {
    const { data } = await client.post<ApiResponse<{ request_ids: string[] }>>(
      '/requests/upload/commit',
      payload
    )
    return data
  },

  downloadODSTemplate: async () => {
    const res = await client.get('/requests/upload/template', {
      responseType: 'blob',
    })
    return res
  },
}
