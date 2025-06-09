# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Start both frontend and backend concurrently
npm start

# Or run separately:
# Backend (FastAPI on port 8000)
python main.py

# Frontend (Vite dev server on port 3000)
npm run dev
```

### Build & Production
```bash
# Build frontend for production
npm run build

# Run production server
python main.py
```

### Code Quality
```bash
# Run frontend linter
npm run lint

# Run backend tests
python test_api.py
python test_transcript.py
```

## Architecture Overview

This is a YouTube chat organizer application with a React frontend and FastAPI backend that allows users to:
1. Manually add YouTube videos to their library
2. Chat with an AI (Gemini 2.5 Flash Preview) about their video content
3. Get video recommendations (discovery mode) or synthesized answers from transcripts (synthesis mode)
4. Organize videos by automatically extracted topics

### Key Architecture Decisions

1. **Manual Video Curation**: Videos are added individually by URL rather than automatic library sync
2. **Dual Response Modes**: 
   - Discovery: Find relevant videos in library
   - Synthesis: Get answers from transcripts with clickable timestamp citations
3. **Local Storage**: All data stored in SQLite database (`data/project_insight.db`)
4. **State Management**: Frontend uses Zustand for chat state
5. **API Communication**: Axios with proxy configuration in Vite for development

### Database Schema

- **videos**: Stores video metadata, transcript, and topic assignment
- **conversations**: Chat session tracking
- **messages**: Chat history with role and content
- **topics**: Automatically extracted topic categories

### Migration System

Migrations are in `migrations/` directory. The system tracks applied migrations and includes backup functionality before schema changes.

### API Configuration

Three API keys required (configured via UI or .env):
- `GOOGLE_AI_API_KEY`: For Gemini AI model
- `YOUTUBE_API_KEY`: For YouTube Data API v3
- `GOOGLE_CLOUD_PROJECT_ID`: For Google Cloud services

### Important Files

- **config.py**: Centralized configuration using Pydantic BaseSettings
- **chat_handler.py**: Core logic for determining response mode and crafting prompts
- **topic_service.py**: Handles automatic topic extraction and management
- **src/hooks/useChat.js**: Zustand store for chat state management

## Recent Updates

### UI/UX Improvements

1. **YouTube Link Fix in VideoCard Component**:
   - Fixed click functionality for "Watch on YouTube" overlay
   - Updated component to handle different field names from various API endpoints (e.g., `video_id` vs `id`, `thumbnail_url` vs `thumbnail`)
   - Made video thumbnails and titles clickable to open YouTube videos
   - Added proper event handling to prevent conflicts with topic selector

2. **Topic Management Enhancement**:
   - Topic creation is fully functional - users can create new topics by typing them when adding/editing video topics
   - Backend automatically creates new topics via `get_or_create_topic` method
   - Topics are normalized (converted to snake_case) for consistency

3. **Modern Button Styling**:
   - Redesigned "Back to Topics" button with modern aesthetics
   - Added gradient backgrounds, smooth animations, and hover effects
   - Implemented dark mode support with appropriate styling
   - Used cubic-bezier transitions for smooth movements

### Technical Notes

- VideoCard component now handles both naming conventions from different API endpoints
- CSS uses `pointer-events` management to prevent overlay blocking clicks
- Topic selector properly prevents event propagation to avoid navigation conflicts