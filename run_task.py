#!/usr/bin/env python3
"""
Flexible Browser-Use Task Runner
Run any task by passing it as a command-line argument or environment variable
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


async def run_task(task: str):
    """Run a Browser-Use task"""
    # Check if API key is set
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY not found in .env file")
        sys.exit(1)
    
    print(f"✅ API key loaded (starts with: {api_key[:10]}...)")
    
    # Using Google Gemini
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
            headless=False,
            enable_default_extensions=False,
            user_data_dir=str(user_data_dir),
            args=['--no-sandbox', '--disable-dev-shm-usage'],
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
    
    print(f"\n🤖 Task: {task}")
    print("="*50)
    
    history = await agent.run()
    
    # Copy screenshots to our screenshots folder
    screenshot_paths = history.screenshot_paths()
    if screenshot_paths:
        print(f"\n📸 Found {len(screenshot_paths)} screenshot(s)")
        for i, screenshot_path in enumerate(screenshot_paths, 1):
            if screenshot_path and Path(screenshot_path).exists():
                # Create a timestamped filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Include task name in filename (sanitized)
                task_slug = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in task[:30]).strip().replace(' ', '_')
                dest_path = screenshots_dir / f"{task_slug}_{timestamp}_{i}.png"
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
    
    return history


async def main():
    # Get task from: command line > environment variable > default
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    elif os.getenv("BROWSER_USE_TASK"):
        task = os.getenv("BROWSER_USE_TASK")
    else:
        print("Usage: python run_task.py 'your task here'")
        print("\nOr set environment variable: export BROWSER_USE_TASK='your task'")
        print("\nExamples:")
        print("  python run_task.py 'Search for Python tutorials on YouTube'")
        print("  python run_task.py 'Find the weather in San Francisco'")
        print("  python run_task.py 'Go to github.com and find the most popular Python repository'")
        sys.exit(1)
    
    try:
        await run_task(task)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
