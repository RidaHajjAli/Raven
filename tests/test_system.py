import asyncio
import aiohttp
from pathlib import Path

async def test_api_endpoints():
    """Test all API endpoints"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing API Endpoints")
        print("=" * 40)
        
        # Test health endpoint
        try:
            async with session.get(f"{base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Health check: PASSED")
                    print(f"   Status: {data['status']}")
                else:
                    print("❌ Health check: FAILED")
        except Exception as e:
            print(f"❌ Health check: ERROR - {e}")
        
        # Test status endpoint
        try:
            async with session.get(f"{base_url}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Status endpoint: PASSED")
                    print(f"   Running: {data['is_running']}")
                    print(f"   Links generated: {data['links_generated']}")
                else:
                    print("❌ Status endpoint: FAILED")
        except Exception as e:
            print(f"❌ Status endpoint: ERROR - {e}")
        
        # Test start endpoint
        try:
            async with session.post(f"{base_url}/start") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Start processing: PASSED")
                    print(f"   Message: {data['message']}")
                else:
                    print("❌ Start processing: FAILED")
        except Exception as e:
            print(f"❌ Start processing: ERROR - {e}")
        
        # Wait a bit for processing
        print("\n⏳ Waiting 30 seconds for processing...")
        await asyncio.sleep(30)
        
        # Check status again
        try:
            async with session.get(f"{base_url}/status") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Status after processing: PASSED")
                    print(f"   Running: {data['is_running']}")
                    print(f"   Links generated: {data['links_generated']}")
                    print(f"   Valid links: {data['valid_links']}")
                    print(f"   Insights extracted: {data['insights_extracted']}")
        except Exception as e:
            print(f"❌ Status check: ERROR - {e}")
        
        # Test insights endpoint
        try:
            async with session.get(f"{base_url}/insights") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Insights endpoint: PASSED")
                    print(f"   Total insights: {len(data)}")
                    if data:
                        print(f"   Sample insight: {data[0]['main_topic']}")
                else:
                    print("❌ Insights endpoint: FAILED")
        except Exception as e:
            print(f"❌ Insights endpoint: ERROR - {e}")
        
        # Test stop endpoint
        try:
            async with session.post(f"{base_url}/stop") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Stop processing: PASSED")
                    print(f"   Message: {data['message']}")
                else:
                    print("❌ Stop processing: FAILED")
        except Exception as e:
            print(f"❌ Stop processing: ERROR - {e}")

def check_file_outputs():
    """Check if files are being created"""
    print("\n📁 Checking File Outputs")
    print("=" * 40)
    
    # Check valid_jsons directory
    valid_jsons_dir = Path("valid_jsons")
    if valid_jsons_dir.exists():
        json_files = list(valid_jsons_dir.glob("*.json"))
        print(f"✅ Valid JSONs directory: {len(json_files)} files")
        if json_files:
            print(f"   Sample file: {json_files[0].name}")
    else:
        print("❌ Valid JSONs directory: Not found")
    
    # Check insights_json directory
    insights_dir = Path("insights_json")
    if insights_dir.exists():
        insight_files = list(insights_dir.glob("*.json"))
        print(f"✅ Insights directory: {len(insight_files)} files")
        if insight_files:
            print(f"   Sample file: {insight_files[0].name}")
    else:
        print("❌ Insights directory: Not found")
    
    # Check log file
    log_file = Path("app.log")
    if log_file.exists():
        print(f"✅ Log file: {log_file.stat().st_size} bytes")
    else:
        print("❌ Log file: Not found")

async def main():
    """Main test function"""
    print("🚀 ChatGPT Link Processor - System Test")
    print("=" * 50)
    print()
    print("This script will test the running system.")
    print("Make sure the server is running with: python run.py")
    print()
    
    input("Press Enter to start testing...")
    
    await test_api_endpoints()
    check_file_outputs()
    
    print("\n" + "=" * 50)
    print("🎯 Test Complete!")
    print("Check the output above for any failed tests.")
    print("For detailed logs, check app.log file.")

if __name__ == "__main__":
    asyncio.run(main())