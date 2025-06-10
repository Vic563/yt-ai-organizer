import axios from 'axios'
import { getToken, refreshAccessToken, clearAuth } from './auth'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      
      try {
        const newToken = await refreshAccessToken()
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      } catch (refreshError) {
        // Refresh failed, redirect to login
        clearAuth()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }
    
    return Promise.reject(error)
  }
)

// Configuration endpoints
export const checkConfiguration = async () => {
  const response = await api.get('/config/check')
  return response.data
}

export const updateConfiguration = async (config) => {
  const response = await api.post('/config/update', config)
  return response.data
}

// Video management
export const addVideo = async (videoUrl) => {
  const response = await api.post('/videos/add', { url: videoUrl })
  return response.data
}

export const removeVideo = async (videoId) => {
  const response = await api.delete(`/videos/${videoId}`)
  return response.data
}

export const getAllVideos = async () => {
  const response = await api.get('/videos')
  return response.data
}

export const getLibraryStats = async () => {
  const response = await api.get('/library/stats')
  return response.data
}

// Chat endpoints
export const sendChatMessage = async (message, conversationHistory = []) => {
  const response = await api.post('/chat/message', {
    message,
    conversation_history: conversationHistory
  })
  return response.data
}

export const getChatHistory = async (conversationId) => {
  const response = await api.get(`/chat/history/${conversationId}`)
  return response.data
}

export const exportConversation = async (messages, format, title = 'Conversation History') => {
  const response = await api.post('/chat/export', {
    messages,
    format,
    title
  })
  return response.data
}

// Error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    throw error
  }
)

export default api
