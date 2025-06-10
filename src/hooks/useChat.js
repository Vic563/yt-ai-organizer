import { create } from 'zustand'
import { exportConversation as apiExportConversation } from '../services/api'

export const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  conversationId: null,

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      ...message
    }]
  })),

  setLoading: (loading) => set({ isLoading: loading }),

  clearChat: () => set({ 
    messages: [], 
    conversationId: null 
  }),

  setConversationId: (id) => set({ conversationId: id }),

  getConversationHistory: () => {
    const { messages } = get()
    return messages.map(msg => ({
      role: msg.type === 'user' ? 'user' : 'assistant',
      content: msg.content
    }))
  },

  exportConversation: async (format) => {
    const { messages } = get()
    
    if (messages.length === 0) {
      throw new Error('No conversation to export')
    }

    const timestamp = new Date().toISOString().split('T')[0]
    const title = `Conversation_${timestamp}`
    
    const response = await apiExportConversation(messages, format, title)
    
    // Handle the download based on format
    if (format === 'pdf') {
      // For PDF, response.content is base64 encoded
      const byteCharacters = atob(response.content)
      const byteNumbers = new Array(byteCharacters.length)
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
      }
      const byteArray = new Uint8Array(byteNumbers)
      const blob = new Blob([byteArray], { type: response.content_type })
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = response.filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } else {
      // For markdown and text, create blob directly from content
      const blob = new Blob([response.content], { type: response.content_type })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = response.filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    }
    
    return response
  }
}))
