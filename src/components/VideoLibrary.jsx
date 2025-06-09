import React, { useState, useEffect } from 'react'
import { Plus, Trash2, ExternalLink, Video, AlertCircle, CheckCircle, Loader } from 'lucide-react'
import { addVideo, removeVideo, getAllVideos } from '../services/api'

const VideoLibrary = ({ onClose }) => {
  const [videos, setVideos] = useState([])
  const [newVideoUrl, setNewVideoUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingVideos, setIsLoadingVideos] = useState(true)
  const [status, setStatus] = useState({ type: '', message: '' })

  useEffect(() => {
    loadVideos()
  }, [])

  const loadVideos = async () => {
    try {
      setIsLoadingVideos(true)
      const response = await getAllVideos()
      setVideos(response.videos || [])
    } catch (error) {
      console.error('Failed to load videos:', error)
      setStatus({ type: 'error', message: 'Failed to load video library' })
    } finally {
      setIsLoadingVideos(false)
    }
  }

  const handleAddVideo = async (e) => {
    e.preventDefault()
    if (!newVideoUrl.trim()) return

    setIsLoading(true)
    setStatus({ type: '', message: '' })

    try {
      const result = await addVideo(newVideoUrl.trim())
      
      if (result.success) {
        setStatus({ 
          type: 'success', 
          message: result.message 
        })
        setNewVideoUrl('')
        // Reload videos to show the new addition
        await loadVideos()
      } else {
        setStatus({ 
          type: 'error', 
          message: result.message 
        })
      }
    } catch (error) {
      setStatus({ 
        type: 'error', 
        message: error.response?.data?.detail || 'Failed to add video' 
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleRemoveVideo = async (videoId, title) => {
    if (!confirm(`Are you sure you want to remove "${title}" from your library?`)) {
      return
    }

    try {
      const result = await removeVideo(videoId)
      
      if (result.success) {
        setStatus({ 
          type: 'success', 
          message: 'Video removed successfully' 
        })
        // Reload videos to reflect the removal
        await loadVideos()
      } else {
        setStatus({ 
          type: 'error', 
          message: result.message 
        })
      }
    } catch (error) {
      setStatus({ 
        type: 'error', 
        message: 'Failed to remove video' 
      })
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return ''
    return new Date(dateString).toLocaleDateString()
  }

  const formatDuration = (duration) => {
    if (!duration) return ''
    
    // Convert ISO 8601 duration (PT4M13S) to readable format
    const match = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/)
    if (!match) return duration
    
    const hours = parseInt(match[1]) || 0
    const minutes = parseInt(match[2]) || 0
    const seconds = parseInt(match[3]) || 0
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    }
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  return (
    <div className="video-library">
      <div className="library-header">
        <h2>Video Library</h2>
        <button className="btn-icon" onClick={onClose}>
          <Plus size={20} style={{ transform: 'rotate(45deg)' }} />
        </button>
      </div>

      <div className="library-content">
        {/* Add Video Form */}
        <div className="add-video-section">
          <h3>Add Video to Library</h3>
          <p>Paste a YouTube video URL to add it to your curated collection:</p>
          
          <form onSubmit={handleAddVideo} className="add-video-form">
            <div className="input-container">
              <input
                type="url"
                value={newVideoUrl}
                onChange={(e) => setNewVideoUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                disabled={isLoading}
                className="video-url-input"
              />
              <button
                type="submit"
                disabled={!newVideoUrl.trim() || isLoading}
                className="btn-primary"
              >
                {isLoading ? <Loader size={16} className="spinning" /> : <Plus size={16} />}
                {isLoading ? 'Adding...' : 'Add Video'}
              </button>
            </div>
          </form>

          {status.message && (
            <div className={`status-message ${status.type}`}>
              {status.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              {status.message}
            </div>
          )}
        </div>

        {/* Video Library */}
        <div className="library-section">
          <h3>Your Video Collection ({videos.length} videos)</h3>
          
          {isLoadingVideos ? (
            <div className="loading-state">
              <Loader size={24} className="spinning" />
              <p>Loading your video library...</p>
            </div>
          ) : videos.length === 0 ? (
            <div className="empty-state">
              <Video size={48} />
              <h4>No videos in your library yet</h4>
              <p>Add your first video using the form above to start building your curated collection.</p>
            </div>
          ) : (
            <div className="video-list">
              {videos.map((video) => (
                <div key={video.video_id} className="video-item">
                  <div className="video-thumbnail">
                    {video.thumbnail_url ? (
                      <img src={video.thumbnail_url} alt={video.title} />
                    ) : (
                      <div className="thumbnail-placeholder">
                        <Video size={24} />
                      </div>
                    )}
                    {video.duration && (
                      <span className="duration-badge">
                        {formatDuration(video.duration)}
                      </span>
                    )}
                  </div>
                  
                  <div className="video-details">
                    <h4 className="video-title">{video.title}</h4>
                    <p className="channel-name">{video.channel_title}</p>
                    
                    <div className="video-meta">
                      <span className="publish-date">
                        {formatDate(video.published_at)}
                      </span>
                      {video.has_transcript && (
                        <span className="transcript-badge">
                          <CheckCircle size={14} />
                          Transcript
                        </span>
                      )}
                    </div>
                    
                    {video.description && (
                      <p className="video-description">
                        {video.description.length > 150 
                          ? `${video.description.substring(0, 150)}...` 
                          : video.description
                        }
                      </p>
                    )}
                  </div>
                  
                  <div className="video-actions">
                    <button
                      className="btn-icon"
                      onClick={() => window.open(`https://www.youtube.com/watch?v=${video.video_id}`, '_blank')}
                      title="Watch on YouTube"
                    >
                      <ExternalLink size={16} />
                    </button>
                    <button
                      className="btn-icon danger"
                      onClick={() => handleRemoveVideo(video.video_id, video.title)}
                      title="Remove from library"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default VideoLibrary
