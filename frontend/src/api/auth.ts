import client from './client'
import type { ApiResponse, TokenResponse, UserOut } from '@/types/api'

export interface LoginPayload {
  identifier: string
  password: string
}

export const authApi = {
  login: async (payload: LoginPayload) => {
    const { data } = await client.post<ApiResponse<TokenResponse>>('/auth/login', payload)
    return data
  },

  refresh: async (refresh_token: string) => {
    const { data } = await client.post<ApiResponse<TokenResponse>>('/auth/refresh', { refresh_token })
    return data
  },

  logout: async (refresh_token: string) => {
    const { data } = await client.post<ApiResponse<{}>>('/auth/logout', { refresh_token })
    return data
  },

  me: async () => {
    const { data } = await client.get<ApiResponse<UserOut>>('/auth/me')
    return data
  },

  createUser: async (payload: CreateUserRequest) => {
    const { data } = await client.post<ApiResponse<UserOut>>('/auth/users', payload)
    return data
  },
}

export interface CreateUserRequest {
  username: string
  email: string
  full_name: string
  password: string
  role_public_id: string
}
