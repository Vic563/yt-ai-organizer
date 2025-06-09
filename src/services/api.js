import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

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

// Error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    throw error
  }
)

export default api
