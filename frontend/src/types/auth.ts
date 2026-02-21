export interface User {
  id: string
  email: string
  role: 'admin' | 'operator'
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
}
