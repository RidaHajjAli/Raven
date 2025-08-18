import asyncio
import logging
import sys
import uvicorn
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app import app
from services.ollama_manager import OllamaManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def startup_checks():
    """Perform startup checks and initialization"""
    logger.info("Starting ChatGPT Link Processor...")
    
    try:
        # Initialize Ollama manager
        ollama_manager = OllamaManager()
        
        # Ensure Ollama service and model are ready
        await ollama_manager.ensure_model_running()
        
        logger.info("All startup checks passed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Startup checks failed: {e}")
        return False

def main():
    """Main entry point"""
    print("="*60)
    print("🚀 ChatGPT Link Processor - Production Server")
    print("="*60)
    print()
    print("Features:")
    print("• Asynchronous link generation using LLM")
    print("• Automatic link validation and content extraction")
    print("• Intelligent insight extraction")
    print("• RESTful API with FastAPI")
    print("• Automatic Ollama service management")
    print()
    print("API Endpoints:")
    print("• POST /start - Start background processing")
    print("• POST /stop - Stop background processing")
    print("• GET /status - Get system status")
    print("• GET /insights - List collected insights")
    print("• GET /health - Health check")
    print("• GET /docs - Interactive API documentation")
    print()
    print("="*60)
    
    try:
        # Run startup checks
        startup_success = asyncio.run(startup_checks())
        
        if not startup_success:
            logger.error("Startup failed. Please check the logs and try again.")
            sys.exit(1)
        
        # Start the FastAPI server
        logger.info("Starting FastAPI server on http://127.0.0.1:8001")
        print("\n🌐 Server starting at: http://127.0.0.1:8001")
        print("📚 API Documentation: http://127.0.0.1:8001/docs")
        print("\nPress Ctrl+C to stop the server")
        print("="*60)
        
        uvicorn.run(
            "app:app",
            host="127.0.0.1",
            port=8001,
            log_level="info",
            reload=True, # Disable in production
            access_log=True,
            use_colors=True
        )
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        print("\n👋 Server stopped gracefully")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()