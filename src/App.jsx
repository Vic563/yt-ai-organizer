import React, { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import ConfigPanel from './components/ConfigPanel';
import VideoLibrary from './components/VideoLibrary';
import TopicsPage from './pages/TopicsPage';
import PerformancePage from './pages/PerformancePage';
import Login from './components/Login';
import Register from './components/Register';
import PrivateRoute from './components/PrivateRoute';
import { useChatStore } from './hooks/useChat';
import { Settings, MessageCircle, Video, Sun, Moon, Folder, BarChart2, LogOut, User } from 'lucide-react';
import { checkConfiguration } from './services/api';
import auth from './services/auth';

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [showConfig, setShowConfig] = useState(false)
  const [showLibrary, setShowLibrary] = useState(false)
  const [isConfigured, setIsConfigured] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(auth.isAuthenticated())
  const [currentUser, setCurrentUser] = useState(null)
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Check localStorage or system preference
    const saved = localStorage.getItem('darkMode')
    if (saved !== null) {
      return JSON.parse(saved)
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })
  const { clearChat } = useChatStore()

  useEffect(() => {
    if (isAuthenticated) {
      checkConfig()
      fetchCurrentUser()
    } else {
      setIsLoading(false)
      setCurrentUser(null)
    }
  }, [isAuthenticated])

  useEffect(() => {
    // Apply theme to document
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light')
    localStorage.setItem('darkMode', JSON.stringify(isDarkMode))
  }, [isDarkMode])

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode)
  }

  const fetchCurrentUser = async () => {
    try {
      const user = await auth.getCurrentUser()
      setCurrentUser(user)
    } catch (error) {
      console.error('Failed to fetch current user:', error)
      setCurrentUser(null)
    }
  }

  const handleLogout = async () => {
    await auth.logout()
    setIsAuthenticated(false)
    setCurrentUser(null)
    clearChat()
    navigate('/login')
  }

  // Removed duplicate useEffect

  const checkConfig = async () => {
    try {
      const response = await checkConfiguration()
      setIsConfigured(response.configured)
    } catch (error) {
      console.error('Failed to check configuration:', error)
      // Set a default configuration for testing purposes
      setIsConfigured(true) // Force to true as a fallback
    } finally {
      setIsLoading(false)
    }
  }

  const handleShowLibrary = () => {
    setShowLibrary(true)
    setShowConfig(false)
  }

  // Check current route for active navigation
  const isConfigPage = location.pathname === '/config';
  const isTopicsPage = location.pathname.startsWith('/topics');
  const isLibraryPage = location.pathname === '/library';
  const isChatPage = location.pathname === '/';
  const isPerformancePage = location.pathname === '/performance';

  if (isLoading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner"></div>
        <p>Loading Project Insight...</p>
      </div>
    )
  }

  // Only show setup screen if not configured and not on any of the main pages
  if (!isConfigured && location.pathname === '/setup') {
    return (
      <div className="app-setup">
        <div className="setup-container">
          <h1>Welcome to Youtube Organizer</h1>
          <p>Your conversational AI partner for exploring your YouTube library.</p>
          <p>Let's get you set up first.</p>
          <button 
            className="btn-primary"
            onClick={() => navigate('/config')}
          >
            Configure API Keys
          </button>
        </div>
        <footer style={{ textAlign: 'center', padding: '10px', fontSize: '0.8em', color: 'grey' }}>Created by Victor Reyes</footer>
      </div>
    )
  }

  return (
    <div className="app">
      {!isConfigPage ? (
        <header className="app-header">
          <div className="header-left">
            <Link to="/" className="flex items-center">
              <MessageCircle size={24} className="mr-2" />
              <h1>Youtube Organizer</h1>
            </Link>
          </div>
          <div className="header-right">
            <Link 
              to="/" 
              className={`btn-icon ${isChatPage ? 'active' : ''}`}
              title="Chat Interface"
            >
              <MessageCircle size={20} />
            </Link>
            <Link 
              to="/topics" 
              className={`btn-icon ${isTopicsPage ? 'active' : ''}`}
              title="Browse by Topic"
            >
              <Folder size={20} />
            </Link>
            <button
              className="btn-icon"
              onClick={toggleTheme}
              title={isDarkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {isDarkMode ? <Sun size={20} /> : <Moon size={20} />}
            </button>
            <Link 
              to="/library" 
              className={`btn-icon ${isLibraryPage ? 'active' : ''}`}
              title="Video Library"
              onClick={handleShowLibrary}
            >
              <Video size={20} />
            </Link>
            <Link 
              to="/config" 
              className={`btn-icon ${isConfigPage ? 'active' : ''}`}
              title="Settings"
            >
              <Settings size={20} />
            </Link>
            <Link 
              to="/performance" 
              className={`btn-icon ${isPerformancePage ? 'active' : ''}`}
              title="Performance"
            >
              <BarChart2 size={20} />
            </Link>
            {isAuthenticated && currentUser && (
              <div className="user-display" title={`Logged in as ${currentUser.username}`}>
                <User size={16} />
                <span className="username">{currentUser.username}</span>
              </div>
            )}
            {isAuthenticated && (
              <button
                className="btn-icon"
                onClick={handleLogout}
                title="Logout"
              >
                <LogOut size={20} />
              </button>
            )}
          </div>
        </header>
      ) : null}

      <main className="app-main">
        <Routes>
          <Route path="/login" element={
            <Login onLogin={() => setIsAuthenticated(true)} />
          } />
          <Route path="/register" element={<Register />} />
          <Route path="/config" element={
            <PrivateRoute>
              <ConfigPanel 
                onClose={() => navigate('/')} 
                onConfigured={async () => {
                  setIsConfigured(true);
                  setShowConfig(false);
                  // Reload configuration status
                  await checkConfig();
                  // Navigate to home page
                  navigate('/');
                }} 
              />
            </PrivateRoute>
          } />
          <Route path="/topics/*" element={
            <PrivateRoute>
              <TopicsPage />
            </PrivateRoute>
          } />
          <Route path="/performance" element={
            <PrivateRoute>
              <PerformancePage />
            </PrivateRoute>
          } />
          <Route path="/library" element={
            <PrivateRoute>
              <VideoLibrary onClose={() => setShowLibrary(false)} />
            </PrivateRoute>
          } />
          <Route path="/" element={
            <PrivateRoute>
              <ChatInterface />
            </PrivateRoute>
          } />
        </Routes>
      </main>
      <footer style={{ textAlign: 'center', padding: '20px', fontSize: '0.9em', color: 'var(--text-color-secondary)' }}>Created by Victor Reyes</footer>
    </div>
  )
}

export default App;
