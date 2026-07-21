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

  changePassword: async (payload: { current_password: string; new_password: string }) => {
    const { data } = await client.post<ApiResponse<Record<string, never>>>('/auth/me/password', payload)
    return data
  },

  updateProfile: async (payload: { username?: string; full_name?: string }) => {
    const { data } = await client.patch<ApiResponse<UserOut>>('/auth/me/profile', payload)
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
