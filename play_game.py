#!/usr/bin/env python3
"""
Browser-Use Game Automation
Interact with the local game running on http://localhost:8080
"""
import os
import sys
import shutil
import time
from pathlib import Path
from datetime import datetime
from browser_use import Agent, Browser, ChatGoogle
from dotenv import load_dotenv
import asyncio

# Load .env from the script's directory
script_dir = Path(__file__).parent
env_path = script_dir / ".env"
load_dotenv(dotenv_path=env_path)

GAME_URL = "http://localhost:8080"


async def check_game_server():
    """Check if the game server is running"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GAME_URL, timeout=aiohttp.ClientTimeout(total=2)) as response:
                return response.status == 200
    except:
        return False


async def main():
    # Check if API key is set
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY not found in .env file")
        sys.exit(1)
    
    # Check if game server is running
    print("🔍 Checking if game server is running...")
    if not await check_game_server():
        print(f"❌ Game server not found at {GAME_URL}")
        print("\nPlease start the game server first:")
        print("  ./start_game.sh")
        print("\nOr manually:")
        print("  cd template-youtube-playables")
        print("  npm run dev")
        sys.exit(1)
    
    print(f"✅ Game server is running at {GAME_URL}")
    
    # Get task from command line or use default
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = f"Navigate to {GAME_URL} and play the game. Click the start button and interact with the basketball game."
    
    print(f"\n🤖 Task: {task}")
    print("="*50)
    
    # Using Google Gemini (supports vision - important for games!)
    llm = ChatGoogle(model="gemini-flash-latest")
    
    # Choose browser mode
    USE_CDP = os.getenv("USE_CDP", "false").lower() == "true"
    
    if USE_CDP:
        print("🔗 Using existing Chrome browser via CDP...")
        browser = Browser(cdp_url="http://localhost:9222")
    else:
        user_data_dir = script_dir / ".browser_data"
        user_data_dir.mkdir(exist_ok=True)
        print("🌐 Launching new browser instance...")
        browser = Browser(
            headless=False,  # Show browser window so you can see the game
            enable_default_extensions=False,
            user_data_dir=str(user_data_dir),
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
    
    # Create screenshots directory
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Enable vision mode - CRITICAL for games since they're visual/Canvas-based
    # Games often don't have traditional DOM elements, so vision is essential
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision=True,  # Always use vision for games (they're visual!)
        vision_detail_level="high",  # High detail for better game element detection
    )
    
    print("\n👁️  Vision mode enabled - agent can see and interact with the game")
    print("Games are visual, so vision is essential for clicking/interacting\n")
    
    history = await agent.run()
    
    # Copy screenshots to our screenshots folder
    screenshot_paths = history.screenshot_paths()
    if screenshot_paths:
        print(f"\n📸 Found {len(screenshot_paths)} screenshot(s)")
        for i, screenshot_path in enumerate(screenshot_paths, 1):
            if screenshot_path and Path(screenshot_path).exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = screenshots_dir / f"game_{timestamp}_{i}.png"
                shutil.copy2(screenshot_path, dest_path)
                print(f"  ✅ Saved: {dest_path.name}")
    
    print("\n" + "="*50)
    print("✅ Task completed!")
    print("="*50)
    print(f"Final result: {history.final_result()}")
    print(f"Visited URLs: {history.urls()}")
    print(f"Number of steps: {history.number_of_steps()}")
    print(f"Total duration: {history.total_duration_seconds():.2f} seconds")
    
    # Show what actions the agent took
    actions = history.action_names()
    if actions:
        print(f"\nActions taken: {', '.join(actions)}")
    
    if screenshot_paths:
        print(f"\nScreenshots saved to: {screenshots_dir}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
