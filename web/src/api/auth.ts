import { post } from './client'
import type { LoginRequest, LoginResponse, RegisterRequest, UserInfo } from '../types'

export function login(data: LoginRequest): Promise<LoginResponse> {
  return post<LoginResponse>('/auth/login', data)
}

export function register(data: RegisterRequest): Promise<UserInfo> {
  return post<UserInfo>('/auth/register', data)
}

export function logout(): Promise<null> {
  return post<null>('/auth/logout')
}

export function fetchCurrentUser(): Promise<UserInfo> {
  return post<UserInfo>('/users/me')
}
