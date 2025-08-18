import asyncio
import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import aiohttp
import psutil
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from config import settings
from services.ollama_manager import OllamaManager
from services.link_generator import LinkGenerator
from services.content_extractor import ContentExtractor
from services.insight_extractor import InsightExtractor

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

# Pydantic models
class SystemStatus(BaseModel):
    is_running: bool
    links_generated: int
    valid_links: int
    insights_extracted: int
    failed_validations: int
    uptime_seconds: float

class InsightSummary(BaseModel):
    filename: str
    user_name: Optional[str]
    main_topic: str
    created_at: str

# Global state
class AppState:
    def __init__(self):
        self.is_running = False
        self.start_time = None
        self.links_generated = 0
        self.valid_links = 0
        self.insights_extracted = 0
        self.failed_validations = 0
        self.background_task = None

app_state = AppState()

# Initialize FastAPI app
app = FastAPI(title="ChatGPT Link Processor", version="1.0.0")

# Initialize services
ollama_manager = OllamaManager()
link_generator = LinkGenerator()
content_extractor = ContentExtractor()
insight_extractor = InsightExtractor()

async def ensure_directories():
    """Ensure required directories exist"""
    Path("valid_jsons").mkdir(exist_ok=True)
    Path("insights_json").mkdir(exist_ok=True)

async def improved_validate_link(session: aiohttp.ClientSession, url: str) -> bool:
    """Improved link validation with better error handling"""
    try:
        # Basic URL format validation
        if not url.startswith("https://chatgpt.com/share/"):
            logger.warning(f"Invalid URL format: {url}")
            return False
        
        # Extract UUID and validate format
        uuid_part = url.split('/')[-1]
        if len(uuid_part) < 20:  # UUIDs should be longer
            logger.warning(f"Invalid UUID format: {uuid_part}")
            return False
        
        # Try to access the link
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        async with session.get(url, headers=headers, timeout=15, allow_redirects=True) as response:
            # Check if we're redirected to login page (indicates private/invalid link)
            final_url = str(response.url)
            if 'auth.openai.com' in final_url or 'login' in final_url.lower():
                logger.info(f"Link requires authentication (private): {url}")
                return False
            
            # Check for common error indicators in the response
            if response.status == 404:
                #logger.info(f"Link not found (404): {url}")
                return False
            elif response.status == 403:
                logger.info(f"Link forbidden (403): {url}")
                return False
            elif response.status >= 400:
                logger.warning(f"Link returned error status {response.status}: {url}")
                return False
            
            # Try to get some content to verify it's a real conversation page
            try:
                content = await response.text()
                
                # Check for error messages in content
                error_indicators = [
                    "conversation not found",
                    "this conversation is private",
                    "unable to load",
                    "something went wrong",
                    "conversation has been deleted"
                ]
                
                content_lower = content.lower()
                for indicator in error_indicators:
                    if indicator in content_lower:
                        logger.info(f"Link contains error indicator '{indicator}': {url}")
                        return False
                
                # Check for positive indicators that this is a valid conversation
                positive_indicators = [
                    "chatgpt",
                    "conversation",
                    "message",
                    "user:",
                    "assistant:"
                ]
                
                positive_count = sum(1 for indicator in positive_indicators if indicator in content_lower)
                if positive_count < 2:
                    logger.info(f"Link doesn't appear to be a conversation page: {url}")
                    return False
                
                logger.info(f"Link validation successful: {url}")
                return True
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout reading content from: {url}")
                return False
            except Exception as e:
                logger.warning(f"Error reading content from {url}: {e}")
                return False
    
    except asyncio.TimeoutError:
        logger.warning(f"Timeout validating link: {url}")
        return False
    except aiohttp.ClientError as e:
        logger.warning(f"Client error validating link {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error validating link {url}: {e}")
        return False

async def process_single_link(session: aiohttp.ClientSession, url: str):
    """Process a single generated link through the entire pipeline"""
    try:
        #logger.info(f"Processing link: {url}")
        
        # Step 1: Validate link with improved validation
        is_valid = await improved_validate_link(session, url)
        if not is_valid:
            #logger.warning(f"Link validation failed: {url}")
            app_state.failed_validations += 1
            return None
        
        app_state.valid_links += 1
        logger.info(f"✅ Link validated successfully: {url}")
        
        # Step 2: Extract complete conversation content (both user and assistant messages)
        conversation_data = await content_extractor.extract_conversation(url)
        if not conversation_data:
            logger.warning(f"No conversation data extracted from: {url}")
            return None

        # Ensure conversation_data is always a dict with 'messages' key
        if isinstance(conversation_data, list):
            conversation_data = {"messages": conversation_data, "url": url}
        elif isinstance(conversation_data, dict):
            if "messages" not in conversation_data:
                # If dict but not in expected format, wrap as messages
                conversation_data = {"messages": [conversation_data], "url": url}
            if "url" not in conversation_data:
                conversation_data["url"] = url
        else:
            logger.warning(f"Conversation data is not a dict or list: {url}")
            return None

        # Validate that we have both user and assistant messages
        message_types = set()
        messages = conversation_data.get('messages', [])
        if isinstance(messages, list):
            message_types = {msg.get('role', 'unknown') for msg in messages if isinstance(msg, dict)}
        
        if not ('user' in message_types or 'human' in message_types):
            logger.warning(f"No user messages found in conversation: {url}")
        
        if not ('assistant' in message_types or 'ai' in message_types):
            logger.warning(f"No assistant messages found in conversation: {url}")
        
        # Skip if we have no meaningful conversation
        if len(messages) < 1:
            logger.warning(f"No messages found in conversation: {url}")
            return None
        
        logger.info(f"Extracted conversation with {len(messages)} messages, types: {message_types}")
        
        # Step 3: Generate title and prepare file paths
        try:
            title = await insight_extractor.generate_title(messages)
        except Exception as e:
            logger.warning(f"Failed to generate title for {url}: {e}")
            title = "Untitled_Conversation"
        
        uuid_str = url.split('/')[-1]
        
        # Sanitize title for filename
        sanitized_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        sanitized_title = sanitized_title[:50] if sanitized_title else "Conversation"
        filename = f"{sanitized_title}_{uuid_str}.json"
        
        # Ensure directories exist
        await ensure_directories()
        
        # Step 4: Save conversation JSON
        filepath = Path("valid_jsons") / filename
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 Conversation saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save conversation {url}: {e}")
            return None
        
        # Step 5: Extract insights only if we have meaningful conversation data
        if len(messages) >= 2:  # At least one exchange
            try:
                insights = await insight_extractor.extract_insights(messages)
                if insights:
                    # Save insights JSON
                    insights_filepath = Path("insights_json") / filename
                    with open(insights_filepath, 'w', encoding='utf-8') as f:
                        json.dump(insights, f, indent=2, ensure_ascii=False)
                    
                    app_state.insights_extracted += 1
                    logger.info(f"💡 Insights saved: {insights_filepath}")
                    
                    return {
                        'url': url,
                        'conversation_file': str(filepath),
                        'insights_file': str(insights_filepath),
                        'message_count': len(messages),
                        'message_types': list(message_types),
                        'title': title
                    }
                else:
                    logger.warning(f"Failed to extract insights from: {url}")
            except Exception as e:
                logger.error(f"Error extracting insights from {url}: {e}")
        else:
            logger.warning(f"Insufficient conversation data for insights extraction: {url}")
        
        return {
            'url': url,
            'conversation_file': str(filepath),
            'message_count': len(messages),
            'message_types': list(message_types),
            'title': title
        }
        
    except Exception as e:
        #logger.error(f"❌ Error processing link {url}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        return None


async def background_worker():
    """Main background worker that continuously generates and processes links"""
    logger.info("Background worker started")
    
    # Create session with better configuration
    timeout = aiohttp.ClientTimeout(total=45, connect=15)
    connector = aiohttp.TCPConnector(
        limit=5,  # Reduce concurrent connections
        limit_per_host=2,
        keepalive_timeout=30,
        enable_cleanup_closed=True
    )
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        consecutive_failures = 0
        
        while app_state.is_running:
            try:
                # Generate new links
                links = link_generator.generate_links(count=20)  # Reduced batch size
                
                if links:
                    app_state.links_generated += len(links)
                    logger.info(f"Generated {len(links)} new links")
                    
                    # Process links with limited concurrency
                    semaphore = asyncio.Semaphore(3)  # Limit concurrent processing
                    
                    async def process_with_semaphore(link):
                        async with semaphore:
                            return await process_single_link(session, link)
                    
                    tasks = [process_with_semaphore(link) for link in links]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Count successful results
                    successful = sum(1 for result in results if result and not isinstance(result, Exception))
                    logger.info(f"Successfully processed {successful}/{len(links)} links")
                    
                    if successful == 0:
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            logger.warning(f"No successful links processed in {consecutive_failures} batches")
                            # Increase wait time after multiple failures
                            await asyncio.sleep(30)
                    else:
                        consecutive_failures = 0
                
                # Rate limiting - wait between batches
                await asyncio.sleep(15)  # Increased delay
                
            except Exception as e:
                logger.error(f"Error in background worker: {e}")
                consecutive_failures += 1
                await asyncio.sleep(10)
    
    logger.info("Background worker stopped")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    await ensure_directories()
    await ollama_manager.ensure_model_running()
    logger.info("Application started successfully")
    
    yield  # Application runs here

    # Shutdown code
    if app_state.is_running:
        app_state.is_running = False
        if app_state.background_task:
            app_state.background_task.cancel()
    logger.info("Application shutdown complete")

app = FastAPI(title="ChatGPT Link Processor", version="1.0.0", lifespan=lifespan)

@app.post("/start")
async def start_processing(background_tasks: BackgroundTasks):
    """Start the background processing"""
    if app_state.is_running:
        raise HTTPException(status_code=400, detail="Processing is already running")
    
    app_state.is_running = True
    app_state.start_time = datetime.now()
    app_state.background_task = asyncio.create_task(background_worker())
    
    logger.info("Processing started")
    return {"message": "Processing started successfully"}

@app.post("/stop")
async def stop_processing():
    """Stop the background processing"""
    if not app_state.is_running:
        raise HTTPException(status_code=400, detail="Processing is not running")
    
    app_state.is_running = False
    if app_state.background_task:
        app_state.background_task.cancel()
        try:
            await app_state.background_task
        except asyncio.CancelledError:
            pass
    
    logger.info("Processing stopped")
    return {"message": "Processing stopped successfully"}

@app.get("/status", response_model=SystemStatus)
async def get_status():
    """Get current system status"""
    uptime = 0
    if app_state.start_time:
        uptime = (datetime.now() - app_state.start_time).total_seconds()
    
    return SystemStatus(
        is_running=app_state.is_running,
        links_generated=app_state.links_generated,
        valid_links=app_state.valid_links,
        insights_extracted=app_state.insights_extracted,
        failed_validations=app_state.failed_validations,
        uptime_seconds=uptime
    )

@app.get("/insights", response_model=List[InsightSummary])
async def get_insights():
    """Get list of collected insights"""
    insights_dir = Path("insights_json")
    if not insights_dir.exists():
        return []
    
    insights = []
    for filepath in insights_dir.glob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            insights.append(InsightSummary(
                filename=filepath.name,
                user_name=data.get('user_name'),
                main_topic=data.get('main_topic', 'Unknown'),
                created_at=data.get('created_at', 'Unknown')
            ))
        except Exception as e:
            logger.error(f"Error reading insight file {filepath}: {e}")
    
    return insights

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "memory_usage": f"{psutil.virtual_memory().percent}%",
        "cpu_usage": f"{psutil.cpu_percent()}%"
    }

@app.get("/debug/test-link")
async def test_single_link(url: str):
    """Debug endpoint to test a single link"""
    async with aiohttp.ClientSession() as session:
        is_valid = await improved_validate_link(session, url)
        return {
            "url": url,
            "is_valid": is_valid
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")