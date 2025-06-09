import React, { useState } from 'react';
import { ExternalLink, Clock, Calendar, Folder } from 'lucide-react';
import TopicSelector from './TopicSelector';

const VideoCard = ({ video }) => {
  const {
    id,
    video_id,
    title,
    thumbnail,
    thumbnail_url,
    duration,
    publishedAt,
    published_at,
    channelTitle,
    channel_title,
    description,
    relevanceReason,
    url
  } = video
  
  // Handle different field names from different API endpoints
  const videoId = id || video_id;
  const thumbnailUrl = thumbnail || thumbnail_url;
  const publishDate = publishedAt || published_at;
  const channel = channelTitle || channel_title;

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

  const formatDate = (dateString) => {
    if (!dateString) return ''
    return new Date(dateString).toLocaleDateString()
  }

  const [currentTopic, setCurrentTopic] = useState(video.topic || video.topic_name || '');

  const handleYouTubeClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    const videoUrl = url || (videoId ? `https://youtube.com/watch?v=${videoId}` : null);
    if (videoUrl) {
      window.open(videoUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const handleTopicChange = (newTopic) => {
    setCurrentTopic(newTopic);
  };

  return (
    <div className="video-card">
      {currentTopic && (
        <div className="video-topic">
          <Folder size={14} />
          <span>{currentTopic}</span>
        </div>
      )}
      <div className="video-thumbnail" onClick={handleYouTubeClick}>
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt={title} />
        ) : (
          <div className="thumbnail-placeholder">
            <ExternalLink size={24} />
          </div>
        )}
        {duration && (
          <span className="duration-badge">
            {formatDuration(duration)}
          </span>
        )}
        <div className="card-overlay" onClick={handleYouTubeClick}>
          <div className="overlay-content">
            <ExternalLink size={20} />
            <span>Watch on YouTube</span>
          </div>
        </div>
      </div>
      
      <div className="video-info">
        <h4 className="video-title" title={title} onClick={handleYouTubeClick}>
          {title}
        </h4>
        
        {channel && (
          <p className="channel-name">{channel}</p>
        )}
        
        <div className="video-meta">
          {publishDate && (
            <span className="publish-date">
              <Calendar size={14} /> {new Date(publishDate).toLocaleDateString()}
            </span>
          )}
          
          <div className="topic-selector-container" onClick={(e) => e.stopPropagation()}>
            <TopicSelector 
              videoId={videoId} 
              currentTopic={currentTopic}
              onTopicChange={handleTopicChange}
            />
          </div>
        </div>
        
        {relevanceReason && (
          <div className="relevance-reason">
            <p><strong>Why this video:</strong> {relevanceReason}</p>
          </div>
        )}
        
        {description && (
          <p className="video-description">
            {description.length > 100 
              ? `${description.substring(0, 100)}...` 
              : description
            }
          </p>
        )}
      </div>
    </div>
  )
}

export default VideoCard
