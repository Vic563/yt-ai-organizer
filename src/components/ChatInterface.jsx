import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User } from 'lucide-react'
import { useChatStore } from '../hooks/useChat'
import { sendChatMessage } from '../services/api'
import VideoCard from './VideoCard'
import ReactMarkdown from 'react-markdown'

const ChatInterface = () => {
  const [inputMessage, setInputMessage] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  
  const { 
    messages, 
    isLoading, 
    addMessage, 
    setLoading, 
    getConversationHistory 
  } = useChatStore()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Ensure input field maintains focus
  useEffect(() => {
    if (inputRef.current && !isLoading) {
      inputRef.current.focus()
    }
  }, [isLoading])

  // Focus input field when component mounts
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!inputMessage.trim() || isLoading) return

    const userMessage = inputMessage.trim()
    setInputMessage('')

    // Refocus the input field immediately after clearing the message
    // Use setTimeout to ensure it happens after the state update
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
      }
    }, 0)

    // Add user message to chat
    addMessage({
      type: 'user',
      content: userMessage
    })

    setLoading(true)

    try {
      // Get conversation history for context
      const history = getConversationHistory()

      // Send message to backend
      const response = await sendChatMessage(userMessage, history)

      // Add AI response to chat
      addMessage({
        type: 'assistant',
        content: response.message,
        videos: response.videos || [],
        citations: response.citations || [],
        responseType: response.type || 'text'
      })
    } catch (error) {
      console.error('Chat error:', error)
      addMessage({
        type: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        error: true
      })
    } finally {
      setLoading(false)
      // Ensure focus is maintained even after loading completes
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus()
        }
      }, 0)
    }
  }

  const renderMessage = (message) => {
    if (message.type === 'user') {
      return (
        <div key={message.id} className="message user-message">
          <div className="message-avatar">
            <User size={20} />
          </div>
          <div className="message-content">
            <p>{message.content}</p>
          </div>
        </div>
      )
    }

    return (
      <div key={message.id} className={`message assistant-message ${message.error ? 'error' : ''}`}>
        <div className="message-avatar">
          <Bot size={20} />
        </div>
        <div className="message-content">
          <div className="message-text">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
          
          {/* Render video recommendations */}
          {message.videos && message.videos.length > 0 && (
            <div className="video-recommendations">
              <h4>Recommended Videos:</h4>
              <div className="video-grid">
                {message.videos.map((video, index) => (
                  <VideoCard key={video.id || index} video={video} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="chat-interface">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <Bot size={48} />
            <h2>Welcome to Youtube Organizer.</h2>
            <p>I'm your AI assistant for exploring your curated YouTube library. Ask me to:</p>
            <ul>
              <li>Find videos on specific topics</li>
              <li>Explain concepts from your videos</li>
              <li>Summarize video content</li>
              <li>Answer questions using your video library</li>
            </ul>
            <p>💡 <strong>Tip:</strong> Use the video library button (📹) in the header to add YouTube videos to your collection first!</p>
            <p>What would you like to explore today?</p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {isLoading && (
          <div className="message assistant-message loading">
            <div className="message-avatar">
              <Bot size={20} />
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="input-container">
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Ask me about your YouTube library or just say hello..."
            disabled={isLoading}
            className="chat-input"
          />
          <button
            type="submit"
            disabled={!inputMessage.trim() || isLoading}
            className="send-button"
          >
            <Send size={20} />
          </button>
        </div>
      </form>
    </div>
  )
}

export default ChatInterface
