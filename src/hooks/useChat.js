import { create } from 'zustand'

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
  }
}))
