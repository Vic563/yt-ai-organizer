# Project Insight

**Your Conversational AI Partner for YouTube Library Exploration**

Project Insight transforms your personal YouTube video library into an interactive, conversational knowledge base. Using Google's Gemini 1.5 Pro AI, you can chat with your entire video collection to discover relevant content and get detailed answers to your questions.

## 🎯 What It Does

- **Conversational Discovery**: Ask "What videos do I have about cooking?" and get personalized recommendations
- **Intelligent Q&A**: Ask "How do you make pasta?" and get answers synthesized from your video transcripts
- **Smart Citations**: Get clickable links to specific video moments that support the AI's answers
- **Context-Aware Chat**: Maintains conversation history for natural, multi-turn discussions

## 🏗️ Architecture

- **Frontend**: React + Vite with modern chat interface
- **Backend**: Python FastAPI with Google AI integration
- **Database**: SQLite for local video metadata storage
- **AI**: Google Gemini 1.5 Pro for conversational responses
- **YouTube Integration**: YouTube Data API v3 + transcript fetching

## 🚀 Quick Start

### Prerequisites

1. **Google AI Studio API Key**: Get from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. **YouTube Data API Key**: Create in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
3. **Google Cloud Project ID**: Find in [Google Cloud Console](https://console.cloud.google.com/)

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd yt-chat-organizer
   ```

2. **Install frontend dependencies**:
   ```bash
   npm install
   ```

3. **Install backend dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Start the application**:
   
   **Terminal 1 - Backend**:
   ```bash
   python main.py
   ```
   
   **Terminal 2 - Frontend**:
   ```bash
   npm run dev
   ```

6. **Open your browser**: Navigate to `http://localhost:3000`

### First-Time Setup

1. **Configure API Keys**: The app will prompt you to enter your API keys on first launch
2. **Sync Your Library**: Click the sync button to fetch your YouTube videos and transcripts
3. **Start Chatting**: Ask questions about your video library!

## 💬 How to Use

### Discovery Queries
Ask about topics to find relevant videos:
- "What videos do I have about machine learning?"
- "Show me cooking videos"
- "Find videos about productivity"

### Synthesis Queries
Ask specific questions to get answers from your content:
- "How do you make sourdough bread?"
- "What is the best way to learn Python?"
- "Explain quantum computing"

### Follow-up Questions
The AI maintains conversation context:
- "Tell me more about that"
- "What about the advanced techniques?"
- "Can you find more videos on this topic?"

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_AI_API_KEY` | Google AI Studio API key | Yes |
| `YOUTUBE_API_KEY` | YouTube Data API key | Yes |
| `GOOGLE_CLOUD_PROJECT_ID` | Google Cloud project ID | Yes |
| `DATABASE_PATH` | SQLite database path | No |
| `TRANSCRIPTS_DIR` | Transcript storage directory | No |
| `GEMINI_MODEL` | Gemini model version | No |
| `MAX_CONVERSATION_HISTORY` | Chat history limit | No |

### Data Storage

- **Database**: `data/project_insight.db` (SQLite)
- **Transcripts**: `data/transcripts/` (Text files)
- **Configuration**: `.env` file

## 🎛️ Features

### ✅ Implemented
- [x] Conversational chat interface
- [x] YouTube library synchronization
- [x] Video transcript fetching and storage
- [x] Extra fallback transcript retrieval using the public timedtext endpoint
- [x] AI-powered video discovery
- [x] Question answering with citations
- [x] Configuration management
- [x] Responsive web design

### 🚧 Planned
- [ ] Advanced search with vector embeddings
- [ ] Cost tracking and optimization
- [ ] Multi-language transcript support
- [ ] Video content summarization
- [ ] Export conversation history

## 🔒 Privacy & Security

- **Local Storage**: All data is stored locally on your machine
- **API Keys**: Stored in environment variables, never transmitted
- **No Cloud Storage**: Your video library data never leaves your device
- **Secure Communication**: HTTPS for all API calls

## 🛠️ Development

### Project Structure
```
├── src/                    # React frontend
│   ├── components/         # UI components
│   ├── hooks/             # React hooks
│   ├── services/          # API services
│   └── styles/            # CSS styles
├── main.py                # FastAPI backend
├── youtube_service.py     # YouTube integration
├── gemini_service.py      # AI integration
├── chat_handler.py        # Chat logic
├── database.py            # Database operations
├── models.py              # Data models
└── config.py              # Configuration
```

### Running Tests
```bash
# Frontend tests
npm test

# Backend tests
python -m pytest
```

### Building for Production
```bash
# Build frontend
npm run build

# Run production server
python main.py
```

## 📊 Cost Management

- **Token Usage**: Displayed in chat interface
- **Conversation Limits**: Configurable history length
- **Transcript Chunking**: Automatic content optimization
- **Efficient Prompting**: Optimized for cost-effective AI usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Report bugs and feature requests on GitHub
- **Documentation**: Check the wiki for detailed guides
- **Community**: Join discussions in GitHub Discussions

## 🙏 Acknowledgments

- Google AI for Gemini 1.5 Pro
- YouTube Data API
- React and FastAPI communities
- Open source contributors

---

**Made with ❤️ for YouTube knowledge explorers**
