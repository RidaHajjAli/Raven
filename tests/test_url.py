import asyncio
import json
import aiohttp
from pathlib import Path
from app import process_single_link, ensure_directories
from services.content_extractor import ContentExtractor
from services.insight_extractor import InsightExtractor

async def test_processing_pipeline(valid_url):
    """Test the complete processing pipeline"""
    print("\n🔄 Starting Unit Test for URL Processing")
    print("=" * 50)
    
    # 1. Ensure directories exist
    await ensure_directories()
    print("✅ Directories ensured")
    
    # 2. Process URL
    print(f"\n🔗 Testing URL: {valid_url}")
    
    try:
        # Create a dummy session (replace with real aiohttp session in production)
        async with aiohttp.ClientSession() as session:
            # 3. Process the link
            await process_single_link(session, valid_url)
            
            # 4. Verify outputs
            print("\n🔍 Verifying outputs...")
            
            # Check conversation file
            conv_file = Path("valid_jsons") / f"{valid_url.split('/')[-1]}.json"
            if conv_file.exists():
                print("✅ Conversation file created")
                with open(conv_file, 'r') as f:
                    conv_data = json.load(f)
                print(f"   → Conversation length: {len(conv_data)} messages")
            else:
                print("❌ Conversation file not found")
                return False
                
            # Check insights file
            insight_file = Path("insights_json") / f"{valid_url.split('/')[-1]}.json"
            if insight_file.exists():
                print("✅ Insights file created")
                with open(insight_file, 'r') as f:
                    insights = json.load(f)
                print(f"   → Main topic: {insights.get('main_topic', 'N/A')}")
                print(f"   → Sentiment: {insights.get('sentiment', 'N/A')}")
            else:
                print("❌ Insights file not found")
                return False
                
            return True
            
    except Exception as e:
        print(f"❌ Error in processing pipeline: {e}")
        return False

if __name__ == "__main__":
    # Test URL (should be a valid ChatGPT share URL)
    TEST_URL = input("Enter a valid ChatGPT share URL for testing: ").strip()
    
    # Run the test
    result = asyncio.run(test_processing_pipeline(TEST_URL))
    
    print("\n" + "=" * 50)
    print("🎯 Test Result: " + ("PASSED" if result else "FAILED"))
    print("Check output files and logs for details")