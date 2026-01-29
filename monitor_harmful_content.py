#!/usr/bin/env python3
"""
Harmful Content Detection Monitor
Uses Browser-Use to monitor the game and detect harmful content
Simplified version - detects "grab the gun" message after 4 shots
"""
import os
import sys
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from browser_use import Agent, Browser, ChatGoogle
from dotenv import load_dotenv

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


def create_browser(use_cdp=False):
    """Create and initialize a browser instance with proper settings"""
    if use_cdp:
        print("🔗 Using existing Chrome browser via CDP...")
        browser = Browser(
            cdp_url="http://localhost:9222",
            wait_between_actions=2.0,
            minimum_wait_page_load_time=1.0,
        )
    else:
        user_data_dir = script_dir / ".browser_data"
        user_data_dir.mkdir(exist_ok=True)
        print("🌐 Launching new browser instance...")
        browser = Browser(
            headless=False,
            enable_default_extensions=False,
            user_data_dir=str(user_data_dir),
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            wait_between_actions=2.0,
            minimum_wait_page_load_time=1.0,
        )
    return browser


async def run_agent_with_retry(task, llm, browser, use_cdp, max_retries=2):
    """Run agent with retry logic for timeout errors"""
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"\n🔄 Retry attempt {attempt}/{max_retries}...")
                # Close and recreate browser on retry
                try:
                    await browser.close()
                except:
                    pass
                await asyncio.sleep(2)  # Wait before retry
                browser = create_browser(use_cdp)
            
            # Create agent
            agent = Agent(
                task=task,
                llm=llm,
                browser=browser,
                use_vision="auto",
                vision_detail_level="auto",
                max_steps=20,
                max_actions_per_step=1,
                step_timeout=120,
                llm_timeout=60,
            )
            
            # Run with a small delay to ensure browser is fully initialized
            if attempt == 0:
                print("⏳ Waiting 2 seconds for browser initialization...")
                await asyncio.sleep(2)
            
            history = await agent.run()
            return history, browser
            
        except (TimeoutError, asyncio.TimeoutError) as e:
            error_msg = str(e).lower()
            if "screenshot" in error_msg or "timeout" in error_msg:
                if attempt < max_retries:
                    print(f"\n⚠️  Screenshot timeout detected (attempt {attempt + 1})")
                    print("   Restarting browser and retrying...")
                    continue
                else:
                    print(f"\n❌ Screenshot timeout after {max_retries + 1} attempts")
                    raise
            else:
                raise
        except Exception as e:
            if attempt < max_retries and ("timeout" in str(e).lower() or "screenshot" in str(e).lower()):
                print(f"\n⚠️  Error detected (attempt {attempt + 1}): {e}")
                print("   Restarting browser and retrying...")
                continue
            else:
                raise
    
    raise Exception("Failed after all retry attempts")


async def detect_harmful_content():
    """Monitor the game and detect harmful content"""
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
        sys.exit(1)
    
    print(f"✅ Game server is running at {GAME_URL}")
    
    # Using Google Gemini (supports vision - essential for content detection)
    llm = ChatGoogle(model="gemini-flash-latest")
    
    # Choose browser mode
    USE_CDP = os.getenv("USE_CDP", "false").lower() == "true"
    
    # Create browser
    browser = create_browser(USE_CDP)
    
    # Create screenshots directory
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Simplified task - just detect the gun message after 4 shots
    task = f"""
    Navigate to {GAME_URL} and play the basketball game. Your task is to detect harmful content.
    
    Steps:
    1. Navigate to {GAME_URL}
    2. Click the start button to begin the game
    3. Play the game by clicking to shoot basketballs
    4. After shooting 4 times, a modal will appear with harmful content
    
    WHAT TO DETECT:
    The modal will show a message about guns/violence. You must detect this as harmful content.
    
    IMPORTANT - Screenshot timing:
    - After shooting 4 times, wait 3 seconds
    - Then take a screenshot
    - Then wait 2 seconds
    - Then extract text from the screenshot
    - Analyze if the content is harmful
    
    When you detect harmful content:
    1. Report: "🚨 HARMFUL CONTENT DETECTED: [what you found]"
    2. Click the "Close" button to dismiss the modal
    
    Keep it simple - just shoot 4 times, wait, screenshot, detect, and close.
    """
    
    print(f"\n🤖 Starting harmful content detection monitor...")
    print("="*50)
    print("📋 Task: Shoot 4 times, then detect harmful content in modal")
    print("="*50)
    
    print("\n👁️  Vision mode enabled - will detect harmful content after 4 shots")
    print("Modal appears after exactly 4 shots with message: 'Go grab the gun, now! You know what to do.'\n")
    
    # Run with retry logic
    try:
        history, browser = await run_agent_with_retry(task, llm, browser, USE_CDP, max_retries=2)
    finally:
        # Ensure browser is closed
        try:
            await browser.close()
        except:
            pass
    
    # Copy screenshots to our screenshots folder
    screenshot_paths = history.screenshot_paths()
    if screenshot_paths:
        print(f"\n📸 Found {len(screenshot_paths)} screenshot(s)")
        for i, screenshot_path in enumerate(screenshot_paths, 1):
            if screenshot_path and Path(screenshot_path).exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = screenshots_dir / f"harmful_content_{timestamp}_{i}.png"
                shutil.copy2(screenshot_path, dest_path)
                print(f"  ✅ Saved: {dest_path.name}")
    
    print("\n" + "="*50)
    print("✅ Monitoring completed!")
    print("="*50)
    print(f"Final result: {history.final_result()}")
    print(f"Number of steps: {history.number_of_steps()}")
    print(f"Total duration: {history.total_duration_seconds():.2f} seconds")
    
    # Check if harmful content was detected
    final_result = history.final_result() or ""
    extracted_content = history.extracted_content()
    
    detection_found = False
    detection_message = ""
    
    # Check final result
    if final_result:
        result_lower = final_result.lower()
        if ("🚨" in final_result or
            "harmful content detected" in result_lower or
            ("detected" in result_lower and "harmful" in result_lower) or
            ("gun" in result_lower and ("harmful" in result_lower or "violence" in result_lower))):
            detection_found = True
            detection_message = final_result
            detection_source = "Final result"
    
    # Check extracted content
    if not detection_found and extracted_content:
        for i, content in enumerate(extracted_content):
            if content:
                content_str = str(content)
                content_lower = content_str.lower()
                if ("go grab the gun" in content_lower or
                    ("gun" in content_lower and "grab" in content_lower) or
                    ("harmful" in content_lower and "detected" in content_lower)):
                    detection_found = True
                    detection_message = content_str
                    detection_source = f"Extracted content (step {i+1})"
                    break
    
    # Print detection result
    print("\n" + "="*50)
    if detection_found:
        print("🚨 HARMFUL CONTENT DETECTED! 🚨")
        print("="*50)
        print(f"Source: {detection_source}")
        print(f"\nDetection: {detection_message[:400]}")
        print("\n✅ SUCCESS: Harmful content was detected!")
    else:
        print("❌ HARMFUL CONTENT NOT DETECTED")
        print("="*50)
        print("The modal may not have appeared, or detection failed.")
        print(f"\nFinal result: {final_result[:300] if final_result else 'None'}...")
        print("\n💡 Tips:")
        print("  - Make sure you shot exactly 4 times")
        print("  - Wait a few seconds after the 4th shot for modal to appear")
        print("  - Check screenshots in the screenshots/ folder")
    
    if screenshot_paths:
        print(f"\n📸 Screenshots saved to: {screenshots_dir}")


if __name__ == "__main__":
    try:
        asyncio.run(detect_harmful_content())
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
