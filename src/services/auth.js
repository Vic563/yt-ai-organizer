import axios from 'axios'

const API_BASE_URL = '/api'

// Create a separate axios instance for auth to avoid circular dependencies
const authApi = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token management
const TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const USER_KEY = 'user_info'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const getRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY)
export const getUser = () => {
  const userStr = localStorage.getItem(USER_KEY)
  return userStr ? JSON.parse(userStr) : null
}

export const setTokens = (accessToken, refreshToken) => {
  localStorage.setItem(TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export const setUser = (user) => {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export const clearAuth = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// Auth API endpoints
export const login = async (username, password) => {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)
  
  const response = await authApi.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  
  const { access_token, refresh_token } = response.data
  setTokens(access_token, refresh_token)
  
  // Get user info
  const userInfo = await getCurrentUser(access_token)
  setUser(userInfo)
  
  return response.data
}

export const register = async (username, email, password) => {
  const response = await authApi.post('/auth/register', {
    username,
    email,
    password,
  })
  return response.data
}

export const logout = async () => {
  const token = getToken()
  if (token) {
    try {
      await authApi.post('/auth/logout', {}, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
    } catch (error) {
      console.error('Logout error:', error)
    }
  }
  clearAuth()
}

export const refreshAccessToken = async () => {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    throw new Error('No refresh token available')
  }
  
  const response = await authApi.post('/auth/refresh', {
    refresh_token: refreshToken,
  })
  
  const { access_token, refresh_token: newRefreshToken } = response.data
  setTokens(access_token, newRefreshToken)
  
  return access_token
}

export const getCurrentUser = async (token = null) => {
  const authToken = token || getToken()
  if (!authToken) {
    throw new Error('No auth token available')
  }
  
  const response = await authApi.get('/auth/me', {
    headers: {
      Authorization: `Bearer ${authToken}`,
    },
  })
  
  return response.data
}

// Check if user is authenticated
export const isAuthenticated = () => {
  const token = getToken()
  const user = getUser()
  return !!(token && user)
}

// Check if user is admin
export const isAdmin = () => {
  const user = getUser()
  return user?.is_admin || false
}

export default {
  login,
  register,
  logout,
  refreshAccessToken,
  getCurrentUser,
  isAuthenticated,
  isAdmin,
  getToken,
  getUser,
  clearAuth,
}