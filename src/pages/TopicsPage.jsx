import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Folder, Video as VideoIcon, ArrowLeft, Edit2, Check, X } from 'lucide-react';
import { topicService } from '../services/topicService';
import VideoCard from '../components/VideoCard';

const TopicsPage = () => {
  const [topics, setTopics] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [videos, setVideos] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingTopic, setEditingTopic] = useState(null);
  const [editingName, setEditingName] = useState('');

  // Load all topics
  useEffect(() => {
    const loadTopics = async () => {
      try {
        setIsLoading(true);
        const topicsData = await topicService.getTopics();
        setTopics(topicsData);
        setError(null);
      } catch (err) {
        console.error('Error loading topics:', err);
        setError('Failed to load topics. Please try again later.');
      } finally {
        setIsLoading(false);
      }
    };

    loadTopics();
  }, []);

  // Load videos when a topic is selected
  useEffect(() => {
    if (!selectedTopic) return;

    const loadVideos = async () => {
      try {
        setIsLoading(true);
        const videosData = await topicService.getVideosByTopic(selectedTopic);
        setVideos(videosData);
        setError(null);
      } catch (err) {
        console.error(`Error loading videos for topic ${selectedTopic}:`, err);
        setError('Failed to load videos. Please try again.');
        setVideos([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadVideos();
  }, [selectedTopic]);

  const handleTopicSelect = (topicName) => {
    setSelectedTopic(topicName);
    // Update URL without page reload
    window.history.pushState({}, '', `/topics/${encodeURIComponent(topicName)}`);
  };

  const handleBack = () => {
    setSelectedTopic(null);
    setVideos([]);
    window.history.pushState({}, '', '/topics');
  };

  const handleEditStart = (e, topicName) => {
    e.stopPropagation(); // Prevent topic selection
    setEditingTopic(topicName);
    setEditingName(topicService.formatTopicName(topicName));
  };

  const handleEditCancel = () => {
    setEditingTopic(null);
    setEditingName('');
  };

  const handleEditSave = async () => {
    if (!editingName.trim() || editingName === topicService.formatTopicName(editingTopic)) {
      handleEditCancel();
      return;
    }

    try {
      await topicService.renameTopic(editingTopic, editingName.trim());
      
      // Refresh topics list
      const topicsData = await topicService.getTopics();
      setTopics(topicsData);
      
      // Update selected topic if it was the one being edited
      if (selectedTopic === editingTopic) {
        setSelectedTopic(editingName.trim());
      }
      
      setEditingTopic(null);
      setEditingName('');
    } catch (error) {
      console.error('Error renaming topic:', error);
      setError('Failed to rename topic. Please try again.');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleEditSave();
    } else if (e.key === 'Escape') {
      handleEditCancel();
    }
  };

  if (isLoading && !selectedTopic) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading topics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <p className="error-message">{error}</p>
        <button onClick={() => window.location.reload()} className="btn btn-primary">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="topics-page">
      {selectedTopic ? (
        <div className="topic-videos">
          <div className="page-header">
            <button onClick={handleBack} className="btn-back">
              <ArrowLeft size={18} /> <span>Back to Topics</span>
            </button>
            <h2>
              <Folder size={24} className="icon" />
              {topicService.formatTopicName(selectedTopic)}
            </h2>
            <p className="video-count">{videos.length} videos</p>
          </div>

          {isLoading ? (
            <div className="loading-container">
              <div className="loading-spinner"></div>
              <p>Loading videos...</p>
            </div>
          ) : videos.length > 0 ? (
            <div className="video-grid">
              {videos.map((video) => (
                <VideoCard key={video.video_id} video={video} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <VideoIcon size={48} className="icon" />
              <h3>No videos found</h3>
              <p>No videos have been assigned to this topic yet.</p>
            </div>
          )}
        </div>
      ) : (
        <div className="topics-list">
          <div className="page-header">
            <h2>Topics</h2>
            <p className="subtitle">Browse your videos by topic</p>
          </div>

          {topics.length > 0 ? (
            <div className="topics-grid">
              {topics.map((topic) => (
                <div 
                  key={topic.name}
                  className="topic-card"
                  onClick={() => handleTopicSelect(topic.name)}
                >
                  <div className="topic-icon">
                    <Folder size={32} />
                  </div>
                  
                  {editingTopic === topic.name ? (
                    <div className="topic-edit-container">
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={handleKeyPress}
                        className="topic-edit-input"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                      <div className="topic-edit-actions">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditSave();
                          }}
                          className="btn-edit-action btn-save"
                          title="Save"
                        >
                          <Check size={16} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditCancel();
                          }}
                          className="btn-edit-action btn-cancel"
                          title="Cancel"
                        >
                          <X size={16} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="topic-content">
                      <h3>{topicService.formatTopicName(topic.name)}</h3>
                      <button
                        onClick={(e) => handleEditStart(e, topic.name)}
                        className="btn-edit"
                        title="Edit topic name"
                      >
                        <Edit2 size={16} />
                      </button>
                    </div>
                  )}
                  
                  <p className="video-count">{topic.video_count} video{topic.video_count !== 1 ? 's' : ''}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <Folder size={48} className="icon" />
              <h3>No topics yet</h3>
              <p>Topics will appear here when you add them to your videos.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TopicsPage;
