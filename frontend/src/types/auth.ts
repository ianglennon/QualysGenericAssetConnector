export interface User {
  id: string
  email: string
  is_active: boolean
  must_change_password: boolean
  role: {
    id: string
    name: string
    is_system: boolean
    permissions: string[]
  }
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
}
