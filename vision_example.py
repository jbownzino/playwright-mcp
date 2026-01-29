#!/usr/bin/env python3
"""
Browser-Use Vision Example
Demonstrates how Browser-Use uses vision to understand screenshots and get coordinates
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from browser_use import Agent, Browser, ChatGoogle
from dotenv import load_dotenv
import asyncio

# Load .env from the script's directory
script_dir = Path(__file__).parent
env_path = script_dir / ".env"
load_dotenv(dotenv_path=env_path)


async def main():
    # Check if API key is set
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY not found in .env file")
        sys.exit(1)
    
    print(f"✅ API key loaded (starts with: {api_key[:10]}...)")
    
    # Using Google Gemini (supports vision)
    llm = ChatGoogle(model="gemini-flash-latest")
    
    # Get task from command line or use default
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "Go to example.com and tell me what colors you see on the page"
    
    print(f"🤖 Task: {task}")
    print("="*50)
    
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
            headless=False,
            enable_default_extensions=False,
            user_data_dir=str(user_data_dir),
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
    
    # Create screenshots directory
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Enable vision mode - this allows the agent to "see" screenshots
    # Options:
    # - "auto" (default): Includes screenshot tool but only uses vision when requested
    # - True: Always includes screenshots in every step
    # - False: Never uses vision
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision="auto",  # Enable vision - agent can see screenshots
        vision_detail_level="high",  # Use high detail for better understanding
    )
    
    print("\n👁️  Vision mode enabled - agent can see and understand screenshots")
    print("The agent will analyze screenshots to find elements and coordinates\n")
    
    history = await agent.run()
    
    # Copy screenshots to our screenshots folder
    screenshot_paths = history.screenshot_paths()
    if screenshot_paths:
        print(f"\n📸 Found {len(screenshot_paths)} screenshot(s)")
        for i, screenshot_path in enumerate(screenshot_paths, 1):
            if screenshot_path and Path(screenshot_path).exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = screenshots_dir / f"vision_{timestamp}_{i}.png"
                shutil.copy2(screenshot_path, dest_path)
                print(f"  ✅ Saved: {dest_path.name}")
    
    print("\n" + "="*50)
    print("✅ Task completed!")
    print("="*50)
    print(f"Final result: {history.final_result()}")
    print(f"Visited URLs: {history.urls()}")
    print(f"Number of steps: {history.number_of_steps()}")
    
    # Show what actions the agent took (including vision-based ones)
    actions = history.action_names()
    if actions:
        print(f"\nActions taken: {', '.join(actions)}")
    
    if screenshot_paths:
        print(f"\nScreenshots saved to: {screenshots_dir}")
        print("\n💡 Tip: The agent used these screenshots to understand the page")
        print("   and determine coordinates for clicking/interacting with elements")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
