import React, { useState, useEffect, useRef } from 'react';
import { X, Check, Edit2, Plus } from 'lucide-react';
import { topicService } from '../services/topicService';

const TopicSelector = ({ videoId, currentTopic, onTopicChange }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [topicInput, setTopicInput] = useState(currentTopic || '');
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef(null);

  // Load topic suggestions when the component mounts or when editing starts
  useEffect(() => {
    const loadSuggestions = async () => {
      try {
        const topics = await topicService.getTopics();
        setSuggestions(topics.map(t => t.name));
      } catch (error) {
        console.error('Error loading topic suggestions:', error);
      }
    };

    if (isEditing) {
      loadSuggestions();
    }
  }, [isEditing]);

  const handleSave = async () => {
    if (!topicInput.trim()) {
      // If input is empty, clear the topic
      await handleClear();
      return;
    }

    try {
      setIsLoading(true);
      const normalizedTopic = topicService.normalizeTopicName(topicInput);
      await topicService.updateVideoTopic(videoId, normalizedTopic);
      onTopicChange?.(normalizedTopic);
      setIsEditing(false);
    } catch (error) {
      console.error('Error updating topic:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = async () => {
    try {
      setIsLoading(true);
      await topicService.updateVideoTopic(videoId, '');
      onTopicChange?.('');
      setTopicInput('');
      setIsEditing(false);
    } catch (error) {
      console.error('Error clearing topic:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setTopicInput(suggestion);
    inputRef.current.focus();
  };

  if (isEditing) {
    return (
      <div className="topic-selector">
        <div className="input-with-suggestions">
          <input
            ref={inputRef}
            type="text"
            value={topicInput}
            onChange={(e) => setTopicInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave();
              if (e.key === 'Escape') setIsEditing(false);
            }}
            placeholder="Enter a topic..."
            disabled={isLoading}
            autoFocus
          />
          
          {suggestions.length > 0 && (
            <div className="suggestions-dropdown">
              {suggestions
                .filter(suggestion => 
                  suggestion.toLowerCase().includes(topicInput.toLowerCase()) && 
                  suggestion !== topicInput
                )
                .slice(0, 5)
                .map((suggestion) => (
                  <div 
                    key={suggestion}
                    className="suggestion-item"
                    onClick={() => handleSuggestionClick(suggestion)}
                  >
                    {suggestion}
                  </div>
                ))}
            </div>
          )}
        </div>
        
        <div className="topic-actions">
          <button 
            className="btn-icon btn-confirm"
            onClick={handleSave}
            disabled={isLoading}
            title="Save topic"
          >
            <Check size={16} />
          </button>
          <button 
            className="btn-icon btn-cancel"
            onClick={() => {
              setTopicInput(currentTopic || '');
              setIsEditing(false);
            }}
            disabled={isLoading}
            title="Cancel"
          >
            <X size={16} />
          </button>
          {currentTopic && (
            <button 
              className="btn-icon btn-clear"
              onClick={handleClear}
              disabled={isLoading}
              title="Clear topic"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="topic-display">
      {currentTopic ? (
        <>
          <span className="topic-name">{topicService.formatTopicName(currentTopic)}</span>
          <button 
            className="btn-icon btn-edit"
            onClick={() => {
              setTopicInput(currentTopic);
              setIsEditing(true);
            }}
            title="Edit topic"
          >
            <Edit2 size={14} />
          </button>
        </>
      ) : (
        <button 
          className="btn-icon btn-add"
          onClick={() => setIsEditing(true)}
          title="Add topic"
        >
          <Plus size={14} /> Add Topic
        </button>
      )}
    </div>
  );
};

export default TopicSelector;
