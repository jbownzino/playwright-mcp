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
            wait_between_actions=0.3,  # Reduced from 2.0 - faster actions
            minimum_wait_page_load_time=0.2,  # Reduced from 1.0 - faster page loads
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
            wait_between_actions=0.3,  # Reduced from 2.0 - faster actions
            minimum_wait_page_load_time=0.2,  # Reduced from 1.0 - faster page loads
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
                use_vision=True,  # Always use vision for faster detection
                vision_detail_level="high",  # High detail to read text quickly
                max_steps=50,  # Increased to allow more actions
                max_actions_per_step=3,  # Allow multiple actions per step (shoot faster)
                step_timeout=60,  # Reduced from 120 - faster steps
                llm_timeout=30,  # Reduced from 60 - faster LLM responses
            )
            
            # Run with a small delay to ensure browser is fully initialized
            if attempt == 0:
                print("⏳ Waiting 0.5 seconds for browser initialization...")
                await asyncio.sleep(0.5)
            
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
    
    # Task: Detect all 3 types of harmful content using vision/screenshots
    # IMPORTANT: This is a Canvas-based game (Phaser), so DOM extraction won't work
    # You MUST use screenshots and vision to see the modal content
    task = f"""
    Navigate to {GAME_URL} and play the basketball game. Your task is to detect ALL 3 types of harmful content.
    
    CRITICAL: This is a Canvas-based game. The modal is rendered on a Canvas, NOT in the DOM.
    You CANNOT use extract action to get text from the modal - it won't work!
    You MUST use screenshots and visual analysis to detect the content.
    
    CRITICAL ITERATIVE PROCEDURE - YOU MUST FOLLOW THIS EXACTLY:
    You must detect, report, and dismiss EACH modal ONE AT A TIME. Do NOT try to detect all 3 at once!
    
    THE PROCEDURE (REPEAT FOR EACH OF 3 MODALS):
    1. Shoot basketballs (1-3 shots will trigger a modal)
    2. Take a screenshot to see if a modal appeared
    3. If you see a modal with harmful content:
       a. IMMEDIATELY report the detection using the format below
       b. IMMEDIATELY click the "Close" button to dismiss the modal
       c. Wait for the modal to close
       d. Continue shooting for the NEXT modal
    4. Repeat steps 1-3 until you have detected and dismissed all 3 types
    
    THE 3 HARMFUL MESSAGES TO DETECT (ONE AT A TIME):
    1. "Go grab the gun, now! You know what to do." - Violence/weapons
    2. "Let's go get some drugs" - Drug promotion
    3. "Send me some photos now" - Sexual/inappropriate content
    
    IMPORTANT RULES:
    - You MUST report EACH detection individually (not all at once)
    - You MUST click "Close" after EACH detection (before continuing)
    - The modal stays open until YOU close it - it won't close automatically
    - After closing one modal, shoot 1-3 more times to trigger the next one
    - Do NOT declare task complete until you have detected, reported, and closed all 3 modals
    
    STEPS:
    1. Navigate to {GAME_URL}
    2. Click the start button to begin the game
    3. Shoot basketballs (1-3 shots will trigger the first modal)
    4. Take screenshots after each shot to check for modals
    
    DETECTION METHOD (MUST USE SCREENSHOTS - BE FAST):
    - After each shot, wait 0.5 seconds, then take a screenshot
    - Take screenshots frequently (after every shot) to catch modals quickly
    - Look at the screenshot visually - you will see:
      * A white modal box with red border
      * Warning icon (⚠️) at the top
      * Text message in the middle
      * Dark gray "Close" button at the bottom
    - Read the text message from the screenshot visually
    - Determine which type of harmful content it is:
      * Violence/weapons (gun message)
      * Drug promotion (drugs message)
      * Sexual/inappropriate (photos message)
    - Work quickly: shoot, screenshot, check for modal, repeat
    
    DO NOT try to use extract action on the modal - it's a Canvas element, not DOM text!
    You can ONLY see it by looking at screenshots.
    
    WHEN YOU DETECT HARMFUL CONTENT (REPORT IMMEDIATELY, ONE AT A TIME):
    As soon as you see a modal in a screenshot, you MUST:
    
    STEP 1 - REPORT THE DETECTION (use this exact format):
    "🚨 HARMFUL CONTENT DETECTED 🚨
    I detected harmful content in the modal through semantic analysis.
    Modal text: '[exact text you see in screenshot]'
    Why it's harmful: [explain - violence/weapons/drugs/sexual content, violates ToS, etc.]
    Content type: [violence/weapons/drugs/sexual/inappropriate]
    Semantic understanding: This content promotes [harmful behavior] which violates game terms of service
    Detection method: Semantic analysis of screenshot and visual text recognition"
    
    STEP 2 - CLOSE THE MODAL (REQUIRED - DO NOT SKIP):
    Immediately after reporting, you MUST click the "Close" button (the dark gray button at the bottom of the modal).
    The modal will NOT close automatically - you MUST click it.
    Wait a moment to confirm the modal has closed.
    
    CRITICAL: You MUST close EVERY modal, including the third and final one!
    Even after detecting the third modal, you MUST still click "Close" to dismiss it.
    Do NOT skip closing any modal, including the last one.
    
    STEP 3 - CONTINUE FOR NEXT MODAL (OR COMPLETE IF ALL 3 DONE):
    After closing the modal:
    - If this was modal #1 or #2: Shoot 1-3 more times to trigger the next modal. Take screenshots after each shot.
    - If this was modal #3 (the final one): You can now complete the task.
    Repeat the process: detect → report → close → continue shooting (until all 3 are done).
    
    CRITICAL: You must complete this cycle (detect → report → close) for EACH of the 3 modals separately.
    Do NOT try to detect all 3 at once. Do NOT skip clicking Close on any modal, including the third one.
    The third modal MUST also be closed after detection - do not leave it open!
    
    TASK COMPLETE (ONLY AFTER ALL 3 ARE DETECTED AND CLOSED):
    Once you have detected, reported, and closed ALL 3 modals individually (including closing the third one), then report:
    "✅ TASK COMPLETE: I have successfully detected, reported, and dismissed all 3 types of harmful content:
    1. Violence/weapons: [message] - DETECTED AND CLOSED
    2. Drug promotion: [message] - DETECTED AND CLOSED
    3. Sexual/inappropriate: [message] - DETECTED AND CLOSED
    All 3 modals have been detected, reported, and closed."
    
    Remember: 
    - Use screenshots to see the modal, not DOM extraction
    - Report each detection individually
    - Close each modal before continuing
    - Complete the cycle 3 times (once for each type)
    """
    
    print(f"\n🤖 Starting harmful content detection monitor...")
    print("="*50)
    print("📋 Task: Detect all 3 types of harmful content")
    print("="*50)
    
    print("\n👁️  Vision mode enabled (CRITICAL for Canvas-based games)")
    print("Task: Detect all 3 types of harmful content:")
    print("  1. 'Go grab the gun, now! You know what to do.' (violence/weapons)")
    print("  2. 'Let's go get some drugs' (drug promotion)")
    print("  3. 'Send me some photos now' (sexual/inappropriate)")
    print("\nModal appears randomly after 1-3 shots, stays open until detected")
    print("⚠️  Note: Modal is rendered on Canvas - must use screenshots/vision, NOT DOM extraction\n")
    
    # Run with retry logic
    try:
        history, browser = await run_agent_with_retry(task, llm, browser, USE_CDP, max_retries=2)
    finally:
        # Ensure browser is closed
        try:
            await browser.close()
        except:
            pass
    
    # First, find all detections and map them to screenshot indices
    screenshot_paths = history.screenshot_paths()
    final_result = history.final_result() or ""
    model_outputs = history.model_outputs()
    action_results = history.action_results()
    
    # Track which types have been detected with screenshot indices
    detected_types = {
        'violence': {'detected': False, 'screenshot_idx': None, 'message': None},
        'drugs': {'detected': False, 'screenshot_idx': None, 'message': None},
        'sexual': {'detected': False, 'screenshot_idx': None, 'message': None}
    }
    
    # Collect detections with step indices (to map to screenshots)
    detections = []
    detected_screenshot_indices = set()  # Track which screenshot indices have detections
    
    # Check model outputs for detections (most reliable)
    if model_outputs:
        for step_idx, output in enumerate(model_outputs):
            if output:
                output_str = str(output)
                output_lower = output_str.lower()
                if "🚨" in output_str or "harmful content detected" in output_lower:
                    # Try to extract message and type
                    msg_type = None
                    if "gun" in output_lower or "violence" in output_lower or "weapon" in output_lower:
                        msg_type = 'violence'
                    elif "drug" in output_lower:
                        msg_type = 'drugs'
                    elif "photo" in output_lower or "sexual" in output_lower or "inappropriate" in output_lower:
                        msg_type = 'sexual'
                    
                    # Map step index to screenshot index (screenshots are usually taken around the same step)
                    # Use step_idx as approximation, but clamp to valid range
                    if screenshot_paths:
                        screenshot_idx = min(step_idx, len(screenshot_paths) - 1)
                        detected_screenshot_indices.add(screenshot_idx)
                    
                    detections.append({
                        'step': step_idx + 1,
                        'type': msg_type,
                        'output': output_str,
                        'screenshot_idx': screenshot_idx if screenshot_paths else None
                    })
                    
                    if msg_type and not detected_types[msg_type]['detected']:
                        detected_types[msg_type]['detected'] = True
                        detected_types[msg_type]['screenshot_idx'] = screenshot_idx if screenshot_paths else None
                        # Extract message from output
                        for line in output_str.split('\n'):
                            if 'modal text:' in line.lower() or 'message' in line.lower():
                                detected_types[msg_type]['message'] = line.strip()
                                break
    
    # Check action results as backup
    if action_results:
        for step_idx, result in enumerate(action_results):
            if result:
                result_str = str(result)
                result_lower = result_str.lower()
                if "🚨" in result_str or "harmful content detected" in result_lower:
                    msg_type = None
                    if "gun" in result_lower or "violence" in result_lower or "weapon" in result_lower:
                        msg_type = 'violence'
                    elif "drug" in result_lower:
                        msg_type = 'drugs'
                    elif "photo" in result_lower or "sexual" in result_lower or "inappropriate" in result_lower:
                        msg_type = 'sexual'
                    
                    if screenshot_paths:
                        screenshot_idx = min(step_idx, len(screenshot_paths) - 1)
                        detected_screenshot_indices.add(screenshot_idx)
                    
                    if msg_type and not detected_types[msg_type]['detected']:
                        detected_types[msg_type]['detected'] = True
                        detected_types[msg_type]['screenshot_idx'] = screenshot_idx if screenshot_paths else None
    
    # Only save screenshots where harmful content was detected
    screenshot_file_map = {}  # Map original index to saved filename
    
    if screenshot_paths and detected_screenshot_indices:
        print(f"\n📸 Found {len(detected_screenshot_indices)} screenshot(s) with harmful content detections")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_count = 0
        
        # Sort indices to save in order
        for idx in sorted(detected_screenshot_indices):
            screenshot_path = screenshot_paths[idx]
            if screenshot_path and Path(screenshot_path).exists():
                # Use detection number instead of original index for cleaner filenames
                detection_num = saved_count + 1
                dest_path = screenshots_dir / f"harmful_content_{timestamp}_{detection_num}.png"
                shutil.copy2(screenshot_path, dest_path)
                screenshot_file_map[idx] = dest_path.name
                saved_count += 1
        
        print(f"  ✅ Saved {saved_count} screenshot(s) with detections to {screenshots_dir.name}/")
        
        # Update detected_types with actual filenames
        for msg_type in detected_types:
            if detected_types[msg_type]['screenshot_idx'] is not None:
                idx = detected_types[msg_type]['screenshot_idx']
                detected_types[msg_type]['screenshot'] = screenshot_file_map.get(idx)
    elif screenshot_paths:
        print(f"\n⚠️  Found {len(screenshot_paths)} screenshot(s) but no harmful content detections")
    else:
        print(f"\n⚠️  No screenshots found in history")
    
    # Print concise, demo-friendly summary
    print("\n" + "="*60)
    print("📊 HARMFUL CONTENT DETECTION RESULTS")
    print("="*60)
    
    # Show each detection concisely
    detection_count = sum(1 for dt in detected_types.values() if dt['detected'])
    
    if detection_count > 0:
        print(f"\n✅ Detected {detection_count} of 3 harmful content types:\n")
        
        type_labels = {
            'violence': 'Violence/Weapons',
            'drugs': 'Drug Promotion',
            'sexual': 'Sexual/Inappropriate'
        }
        
        for msg_type, label in type_labels.items():
            dt = detected_types[msg_type]
            status = "✅ DETECTED" if dt['detected'] else "❌ Not detected"
            print(f"  {status} - {label}")
            if dt['detected']:
                if dt['screenshot']:
                    print(f"    📸 Screenshot: {dt['screenshot']}")
                if dt['message']:
                    # Show just the message part
                    msg = dt['message'].replace('Modal text:', '').replace('modal text:', '').strip()
                    if msg:
                        print(f"    💬 Message: {msg[:60]}...")
            print()
    else:
        print("\n⚠️  No harmful content detections found")
        if final_result:
            print(f"   Final result: {final_result[:100]}...")
    
    # Summary
    all_detected = all(dt['detected'] for dt in detected_types.values())
    print("="*60)
    if all_detected:
        print("🎉 SUCCESS: All 3 types detected!")
    else:
        missing = [k for k, v in detected_types.items() if not v['detected']]
        print(f"⚠️  Incomplete: {len(missing)} type(s) not detected")
    print("="*60)
    
    # Quick stats
    print(f"\n📈 Stats: {history.number_of_steps()} steps | {history.total_duration_seconds():.1f}s")
    if screenshot_file_map:
        print(f"📸 Screenshots: {len(screenshot_file_map)} saved to {screenshots_dir.name}/")
    
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
