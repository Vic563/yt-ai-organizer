import React, { useState, useEffect } from 'react'
import { Save, X, Eye, EyeOff, ExternalLink, CheckCircle, AlertCircle } from 'lucide-react'
import { updateConfiguration, checkConfiguration, getAllVideos } from '../services/api'

const ConfigPanel = ({ onClose, onConfigured }) => {
  const [config, setConfig] = useState({
    googleAiApiKey: '',
    youtubeApiKey: '',
    googleCloudProjectId: ''
  })
  const [showKeys, setShowKeys] = useState({
    googleAiApiKey: false,
    youtubeApiKey: false
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState({ type: '', message: '' })
  const [libraryStats, setLibraryStats] = useState(null)

  useEffect(() => {
    loadCurrentConfig()
    loadLibraryStats()
  }, [])

  const loadCurrentConfig = async () => {
    try {
      const response = await checkConfiguration()
      if (response.configured) {
        setConfig({
          googleAiApiKey: response.keys?.googleAiApiKey ? '••••••••••••••••' : '',
          youtubeApiKey: response.keys?.youtubeApiKey ? '••••••••••••••••' : '',
          googleCloudProjectId: response.keys?.googleCloudProjectId || ''
        })
      }
    } catch (error) {
      console.error('Failed to load config:', error)
    }
  }

  const loadLibraryStats = async () => {
    try {
      const response = await getAllVideos()
      const videos = response.videos || []
      const videosWithTranscripts = videos.filter(v => v.has_transcript).length

      setLibraryStats({
        totalVideos: videos.length,
        videosWithTranscripts: videosWithTranscripts,
        lastSync: videos.length > 0 ? Math.max(...videos.map(v => new Date(v.created_at || v.updated_at).getTime())) : null
      })
    } catch (error) {
      console.error('Failed to load library stats:', error)
    }
  }

  const handleInputChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }))
    setStatus({ type: '', message: '' })
  }

  const toggleShowKey = (field) => {
    setShowKeys(prev => ({ ...prev, [field]: !prev[field] }))
  }

  const handleSave = async () => {
    setIsLoading(true)
    setStatus({ type: '', message: '' })

    try {
      const response = await updateConfiguration(config)
      
      if (response.success) {
        setStatus({ 
          type: 'success', 
          message: 'Configuration saved successfully!' 
        })
        setTimeout(() => {
          onConfigured()
        }, 1500)
      } else {
        setStatus({ 
          type: 'error', 
          message: response.message || 'Failed to save configuration' 
        })
      }
    } catch (error) {
      setStatus({ 
        type: 'error', 
        message: error.response?.data?.detail || 'Failed to save configuration' 
      })
    } finally {
      setIsLoading(false)
    }
  }

  const isFormValid = () => {
    return config.googleAiApiKey && 
           config.youtubeApiKey && 
           config.googleCloudProjectId &&
           !config.googleAiApiKey.includes('••••') &&
           !config.youtubeApiKey.includes('••••')
  }

  return (
    <div className="config-panel">
      <div className="config-header">
        <h2>Configuration</h2>
        <button className="btn-icon" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="config-content">
        <div className="config-section">
          <h3>API Keys Setup</h3>
          <p>You'll need to obtain these API keys to use Project Insight:</p>

          <div className="form-group">
            <label htmlFor="googleAiApiKey">
              Google AI Studio API Key
              <a 
                href="https://aistudio.google.com/app/apikey" 
                target="_blank" 
                rel="noopener noreferrer"
                className="help-link"
              >
                <ExternalLink size={14} />
                Get API Key
              </a>
            </label>
            <div className="input-with-toggle">
              <input
                id="googleAiApiKey"
                type={showKeys.googleAiApiKey ? 'text' : 'password'}
                value={config.googleAiApiKey}
                onChange={(e) => handleInputChange('googleAiApiKey', e.target.value)}
                placeholder="Enter your Google AI Studio API key"
                className="config-input"
              />
              <button
                type="button"
                className="toggle-visibility"
                onClick={() => toggleShowKey('googleAiApiKey')}
              >
                {showKeys.googleAiApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="youtubeApiKey">
              YouTube Data API Key
              <a 
                href="https://console.cloud.google.com/apis/credentials" 
                target="_blank" 
                rel="noopener noreferrer"
                className="help-link"
              >
                <ExternalLink size={14} />
                Google Cloud Console
              </a>
            </label>
            <div className="input-with-toggle">
              <input
                id="youtubeApiKey"
                type={showKeys.youtubeApiKey ? 'text' : 'password'}
                value={config.youtubeApiKey}
                onChange={(e) => handleInputChange('youtubeApiKey', e.target.value)}
                placeholder="Enter your YouTube Data API key"
                className="config-input"
              />
              <button
                type="button"
                className="toggle-visibility"
                onClick={() => toggleShowKey('youtubeApiKey')}
              >
                {showKeys.youtubeApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="googleCloudProjectId">
              Google Cloud Project ID
            </label>
            <input
              id="googleCloudProjectId"
              type="text"
              value={config.googleCloudProjectId}
              onChange={(e) => handleInputChange('googleCloudProjectId', e.target.value)}
              placeholder="Enter your Google Cloud Project ID"
              className="config-input"
            />
          </div>
        </div>

        {libraryStats && (
          <div className="config-section">
            <h3>Library Statistics</h3>
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-label">Total Videos</span>
                <span className="stat-value">{libraryStats.totalVideos || 0}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">With Transcripts</span>
                <span className="stat-value">{libraryStats.videosWithTranscripts || 0}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Last Added</span>
                <span className="stat-value">
                  {libraryStats.lastSync
                    ? new Date(libraryStats.lastSync).toLocaleDateString()
                    : 'None'
                  }
                </span>
              </div>
            </div>
          </div>
        )}

        {status.message && (
          <div className={`status-message ${status.type}`}>
            {status.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
            {status.message}
          </div>
        )}

        <div className="config-actions">
          <button
            className="btn-secondary"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={!isFormValid() || isLoading}
          >
            <Save size={16} />
            {isLoading ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfigPanel
