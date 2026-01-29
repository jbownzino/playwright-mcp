"""
Browser-Use Quickstart Example (Open Source)
Find the number 1 post on Show HN

Browser-Use is open-source. You can use it with any supported LLM provider.
This example uses Google Gemini (free tier available).
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
        print(f"\nLooking for .env at: {env_path}")
        print(f".env file exists: {env_path.exists()}")
        print("\nPlease:")
        print("1. Make sure .env file exists in the project root")
        print("2. Get your free Google Gemini API key: https://aistudio.google.com/app/u/1/apikey?pli=1")
        print("3. Add it to .env: GOOGLE_API_KEY=your_key_here")
        print("4. Make sure there are no spaces around the = sign")
        sys.exit(1)
    
    # Verify API key format (Google API keys start with AIza)
    if not api_key.startswith("AIza"):
        print("⚠️  Warning: API key format doesn't look like a Google Gemini key")
        print("Google API keys typically start with 'AIza'")
    
    print(f"✅ API key loaded (starts with: {api_key[:10]}...)")
    
    # Using Google Gemini (free API key available)
    # Get your free key at: https://aistudio.google.com/app/u/1/apikey?pli=1
    llm = ChatGoogle(model="gemini-flash-latest")
    
    # Alternative LLM options (uncomment to use):
    # from browser_use import ChatOpenAI
    # llm = ChatOpenAI(model="gpt-4o-mini")
    #
    # from browser_use import ChatAnthropic
    # llm = ChatAnthropic(model='claude-sonnet-4-20250514', temperature=0.0)
    
    # Get task from command line argument or use default
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        print(f"📝 Task from command line: {task}")
    else:
        task = "Find the number 1 post on Show HN"
        print(f"📝 Using default task: {task}")
    
    print(f"🤖 Starting agent with task: {task}")
    print("="*50)
    
    # Choose browser mode (set USE_CDP=True to use existing Chrome browser)
    USE_CDP = os.getenv("USE_CDP", "false").lower() == "true"
    
    if USE_CDP:
        # Option 1: Use existing browser via CDP (avoids permission issues)
        # Run: ./start_chrome_for_browser_use.sh first
        print("🔗 Using existing Chrome browser via CDP...")
        browser = Browser(cdp_url="http://localhost:9222")
    else:
        # Option 2: Launch new browser (may have permission issues on macOS)
        # Use a project-local directory to avoid system permission requirements
        user_data_dir = script_dir / ".browser_data"
        user_data_dir.mkdir(exist_ok=True)
        
        print("🌐 Launching new browser instance...")
        browser = Browser(
            headless=False,  # Show browser window
            enable_default_extensions=False,  # Skip extensions if network is unavailable
            user_data_dir=str(user_data_dir),  # Use project-local directory
            args=[
                '--no-sandbox',  # May help with permission issues (less secure but fine for local dev)
                '--disable-dev-shm-usage',  # Avoid shared memory issues
            ],
        )
    
    # Create screenshots directory
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Enable vision mode - allows agent to "see" screenshots and understand page layout
    # Options: "auto" (smart, default), True (always), False (never)
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision="auto",  # Agent can see screenshots to understand page and get coordinates
    )
    history = await agent.run()
    
    # Copy screenshots to our screenshots folder
    screenshot_paths = history.screenshot_paths()
    if screenshot_paths:
        print(f"\n📸 Found {len(screenshot_paths)} screenshot(s)")
        for i, screenshot_path in enumerate(screenshot_paths, 1):
            if screenshot_path and Path(screenshot_path).exists():
                # Create a timestamped filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = screenshots_dir / f"screenshot_{timestamp}_{i}.png"
                shutil.copy2(screenshot_path, dest_path)
                print(f"  ✅ Saved: {dest_path.name}")
    
    print("\n" + "="*50)
    print("✅ Task completed!")
    print("="*50)
    print(f"Final result: {history.final_result()}")
    print(f"Visited URLs: {history.urls()}")
    print(f"Number of steps: {history.number_of_steps()}")
    print(f"Total duration: {history.total_duration_seconds():.2f} seconds")
    if screenshot_paths:
        print(f"Screenshots saved to: {screenshots_dir}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except PermissionError as e:
        print(f"\n❌ Permission Error: {e}")
        print("\n🔧 Workaround Options (no system-wide permissions needed):")
        print("\nOption 1: Use existing Chrome browser")
        print("  1. Close Chrome completely")
        print("  2. Run: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("  3. Edit quickstart.py and uncomment the cdp_url line")
        print("\nOption 2: Try running from Terminal (not IDE)")
        print("  Terminal usually has fewer permission restrictions")
        print("\nOption 3: Check if antivirus/firewall is blocking")
        print("  Temporarily disable to test")
        sys.exit(1)
    except Exception as e:
        error_msg = str(e)
        if "Operation not permitted" in error_msg or "PermissionError" in error_msg:
            print(f"\n❌ Permission Error: {e}")
            print("\n🔧 Easy Fix (no system-wide permissions needed):")
            print("\nUse existing Chrome browser instead:")
            print("  1. Run: ./start_chrome_for_browser_use.sh")
            print("  2. Set environment variable: export USE_CDP=true")
            print("  3. Run again: python quickstart.py")
            print("\nOr add to .env file: USE_CDP=true")
        else:
            print(f"\n❌ Error: {e}")
        sys.exit(1)
