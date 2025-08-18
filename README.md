# ChatGPT Link Processor

A production-grade asynchronous system that generates, validates, and processes ChatGPT share links to extract conversations and insights using FastAPI and LLMs.

## Features

- **Asynchronous Processing**: Continuous background processing using asyncio
- **LLM Integration**: Automatic Ollama service management and model handling
- **Link Generation**: Synthetic ChatGPT share URL generation using LLM
- **Content Extraction**: Robust conversation extraction with multiple fallback strategies
- **Insight Analysis**: Structured insight extraction from conversations
- **RESTful API**: FastAPI-based web interface with comprehensive endpoints
- **Production Ready**: Proper logging, error handling, and rate limiting

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright Browsers**
   ```bash
   playwright install chromium
   ```

3. **Install Ollama** (if not already installed)
   - Download from [ollama.com](https://ollama.com)
   - The application will automatically manage Ollama service and models

4. **Configure Environment** (optional)
   ```bash
   cp .env.example .env
   # Edit .env if you want to change default settings
   ```

5. **Run the Application**
   ```bash
   python run.py
   ```

6. **Start using FastAPI**
   - curl -X POST http://127.0.0.1:8001/start (Or from Swagger UI)

7. **Access the API**
   - Server: http://127.0.0.1:8001
   - Documentation: http://127.0.0.1:8001/docs
   - Health Check: http://127.0.0.1:8001/health

## API Endpoints

### Control Endpoints
- `POST /start` - Start background processing
- `POST /stop` - Stop background processing
- `GET /status` - Get system status and statistics

### Data Endpoints
- `GET /insights` - List all collected insights
- `GET /health` - System health check

### Interactive Documentation
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

## Usage Example

```bash
# Start the server
python run.py

# In another terminal, start processing
curl -X POST http://127.0.0.1:8001/start

# Check status
curl http://127.0.0.1:8001/status

# View insights
curl http://127.0.0.1:8001/insights

# Stop processing
curl -X POST http://127.0.0.1:8001/stop
```

## Architecture

```
├── app.py                 # Main FastAPI application
├── run.py                 # Production server launcher
├── config.py              # Configuration management
├── services/
│   ├── ollama_manager.py  # Ollama service management
│   ├── link_generator.py  # Link generation and validation
│   ├── content_extractor.py # Conversation extraction
│   └── insight_extractor.py # Insight analysis
├── valid_jsons/           # Extracted conversations
├── insights_json/         # Generated insights
└── app.log               # Application logs
```

## Configuration

Environment variables (optional):
- `LOCAL_URL`: Ollama API URL (default: http://localhost:11434)
- `LOCAL_LLM_MODEL_NAME`: Model name (default: a small 1B model or less)

## Data Output

### Conversation Files (`valid_jsons/`)
```json
[
  {
    "role": "user",
    "content": "Hello, I need help with Python"
  },
  {
    "role": "assistant", 
    "content": "I'd be happy to help you with Python..."
  }
]
```

### Insight Files (`insights_json/`)
```json
{
  "user_name": "John",
  "user_background": "Python beginner",
  "main_topic": "Python programming help",
  "problem_described": "Need help with Python basics",
  "solution_provided": "Provided Python learning resources",
  "tags": ["python", "programming", "help"],
  "sentiment": "positive",
  "created_at": "2025-01-15T10:30:00"
}
```

## Production Deployment

For production deployment:

1. Use a process manager like systemd or supervisor
2. Configure reverse proxy (nginx/Apache)
3. Set up proper logging and monitoring
4. Use environment-specific configuration
5. Consider using Docker for containerization

## Troubleshooting

- **Ollama Issues**: Check if Ollama service is running and model is available
- **Extraction Failures**: Verify ChatGPT share links are accessible
- **Performance**: Adjust rate limiting and concurrent processing limits
- **Logs**: Check `app.log` for detailed error information

## License

MIT License - see LICENSE file for details