import asyncio
import aiohttp
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.content_extractor import ContentExtractor
from app import improved_validate_link

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_gemini_parsing():
    """Test parsing of a real Gemini share link"""
    url = "https://gemini.google.com/share/3566b17320e8"
    extractor = ContentExtractor()
    
    print(f"🧪 Testing Gemini Parsing for: {url}")
    
    async with aiohttp.ClientSession() as session:
        # Test validation
        is_valid = await improved_validate_link(session, url)
        print(f"✅ Validation: {'PASSED' if is_valid else 'FAILED'}")
        
        if not is_valid:
            print("❌ Skipping extraction test because validation failed.")
            return

        # Test extraction
        data = await extractor.extract_conversation(url)
        
        if data and 'messages' in data:
            messages = data['messages']
            print(f"✅ Extraction: PASSED ({len(messages)} messages found)")
            
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_preview = msg.get('content', '')[:50].replace('\n', ' ')
                print(f"   [{i+1}] {role.upper()}: {content_preview}...")
        else:
            print("❌ Extraction: FAILED (No data extracted)")

if __name__ == "__main__":
    asyncio.run(test_gemini_parsing())
