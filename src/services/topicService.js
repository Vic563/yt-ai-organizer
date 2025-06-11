import api from './api.js';

export const topicService = {
  // Get all topics with video counts
  async getTopics() {
    try {
      const response = await api.get('/topics');
      return response.data.topics || [];
    } catch (error) {
      console.error('Error fetching topics:', error);
      throw error;
    }
  },

  // Get videos for a specific topic
  async getVideosByTopic(topicName) {
    try {
      const response = await api.get(`/topics/${encodeURIComponent(topicName)}/videos`);
      return response.data.videos || [];
    } catch (error) {
      console.error(`Error fetching videos for topic ${topicName}:`, error);
      throw error;
    }
  },

  // Update a video's topic
  async updateVideoTopic(videoId, topicName) {
    try {
      const response = await api.put(
        `/videos/${videoId}/topic`,
        { topic_name: topicName }
      );
      return response.data;
    } catch (error) {
      console.error(`Error updating topic for video ${videoId}:`, error);
      throw error;
    }
  },

  // Format topic name for display
  formatTopicName(topic) {
    if (!topic) return '';
    // Convert from snake_case to Title Case
    return topic
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  },

  // Format topic name for API (convert to snake_case)
  normalizeTopicName(topic) {
    if (!topic) return '';
    return topic
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .replace(/\s+/g, '_');
  },

  // Rename a topic
  async renameTopic(oldName, newName) {
    try {
      const response = await api.put('/topics/rename', {
        old_name: oldName,
        new_name: newName
      });
      return response.data;
    } catch (error) {
      console.error(`Error renaming topic from ${oldName} to ${newName}:`, error);
      throw error;
    }
  }
};

export default topicService;
