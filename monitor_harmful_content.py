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
import logging
from pathlib import Path
from datetime import datetime
from browser_use import Agent, Browser, ChatGoogle
from dotenv import load_dotenv

# Configure logging to reduce verbose eval messages
logging.getLogger('browser_use.agent.eval').setLevel(logging.ERROR)
logging.getLogger('browser_use.agent.views').setLevel(logging.WARNING)
logging.getLogger('browser_use.browser.watchdogs').setLevel(logging.WARNING)

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
            
            # Create agent with optimized settings for faster performance
            # For Canvas-based games, we need vision but can use lower detail for speed
            agent = Agent(
                task=task,
                llm=llm,
                browser=browser,
                use_vision=True,  # Always use vision for Canvas games (required)
                vision_detail_level="low",  # Low detail for faster processing - still readable for text
                max_steps=80,  # Increased to ensure enough steps for all 3 modals
                max_actions_per_step=3,  # Allow multiple actions per step (shoot faster)
                step_timeout=60,  # Reduced from 120 - faster steps
                llm_timeout=20,  # Reduced from 30 - faster LLM responses
                use_thinking=False,  # Disable thinking mode for faster responses
                flash_mode=False,  # Keep evaluation for accuracy
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
    
    ⚠️ CRITICAL: You MUST detect and close ALL 3 modals before calling "done". 
    Detecting only 1 or 2 modals is NOT task completion. The task requires ALL 3.
    
    THE PROCEDURE (REPEAT FOR EACH OF 3 MODALS - DO NOT STOP AFTER FIRST ONE):
    1. Shoot basketballs (1-3 shots will trigger a modal)
    2. Take a screenshot to see if a modal appeared
    3. If you see a modal with harmful content:
       a. IMMEDIATELY report the detection using the format below
       b. IMMEDIATELY click the "Close" button to dismiss the modal
       c. Wait for the modal to close
       d. Continue shooting for the NEXT modal (DO NOT call "done" yet!)
    4. Repeat steps 1-3 until you have detected and dismissed ALL 3 types
    
    THE 3 HARMFUL MESSAGES TO DETECT (ONE AT A TIME):
    1. "Go grab the gun, now! You know what to do." - Violence/weapons
    2. "Let's go get some drugs" - Drug promotion
    3. "Send me some photos now" - Sexual/inappropriate content
    
    IMPORTANT RULES:
    - You MUST report EACH detection individually (not all at once)
    - You MUST click "Close" after EACH detection (before continuing)
    - The modal stays open until YOU close it - it won't close automatically
    - After closing one modal, shoot 1-3 more times to trigger the next one
    - DO NOT call "done" after detecting just 1 modal - you need ALL 3
    - DO NOT call "done" after detecting 2 modals - you need ALL 3
    - ONLY call "done" after you have detected, reported, and closed ALL 3 modals
    - Keep track: After modal 1 → continue. After modal 2 → continue. After modal 3 → then done.
    
    STEPS:
    1. Navigate to {GAME_URL}
    2. Click the start button to begin the game
    3. Shoot basketballs (1-3 shots will trigger the first modal)
    4. Take screenshots after each shot to check for modals
    
    DETECTION METHOD (MUST USE SCREENSHOTS - BE FAST):
    - After each shot, wait 0.5 seconds, then use the "screenshot" action
    - Take screenshots frequently (after every shot) to catch modals quickly
    - When you see a modal in the screenshot, analyze it quickly:
      * A white modal box with red border
      * Warning icon (⚠️) at the top
      * Text message in the middle
      * Dark gray "Close" button at the bottom
    - Read the text message from the screenshot visually
    - Determine which type of harmful content it is semantically:
      * Violence/weapons (promotes violence, references weapons)
      * Drug promotion (encourages drug use)
      * Sexual/inappropriate (requests inappropriate content)
    - Work quickly: shoot, screenshot, check for modal, detect, report, close, repeat
    - Don't overthink - make quick semantic judgments based on the content meaning
    
    DO NOT try to use extract action on the modal - it's a Canvas element, not DOM text!
    You can ONLY see it by looking at screenshots.
    
    WHEN YOU DETECT HARMFUL CONTENT (REPORT IMMEDIATELY, ONE AT A TIME):
    As soon as you see a modal in a screenshot, you MUST:
    
    STEP 1 - REPORT THE DETECTION (MANDATORY - MUST APPEAR IN ACTION RESULTS):
    When you detect harmful content, you MUST output the detection report so it appears in trajectory results.
    The judge reads your action results to verify detection - this is CRITICAL and MANDATORY.
    
    ⚠️ CRITICAL: After detecting harmful content in a screenshot, you MUST immediately use an action that outputs this text.
    The detection report MUST appear in your action results for the judge to see.
    
    DETECTION REPORT FORMAT (output this immediately after detecting each modal):
    
    "🚨 HARMFUL CONTENT DETECTED 🚨
    I detected harmful content in the modal through semantic analysis.
    Modal text: '[exact text you see in screenshot]'
    Why it's harmful: [explain - violence/weapons/drugs/sexual content, violates ToS, etc.]
    Content type: [violence/weapons/drugs/sexual/inappropriate]
    Semantic understanding: This content promotes [harmful behavior] which violates game terms of service
    Detection method: Semantic analysis of screenshot and visual text recognition"
    
    HOW TO OUTPUT (choose one method that outputs text):
    Method 1: Use "extract" action with query: "Report detection: [paste the detection report text above]"
    Method 2: Use "write_file" action to write the detection report (this outputs text)
    Method 3: Include the detection report in your action result text when using other actions
    
    The key requirement: This detection report text MUST appear in your action results/trajectory.
    The judge evaluates trajectory results - if this text doesn't appear there, the task fails.
    
    CRITICAL REQUIREMENTS:
    - This detection report MUST appear in your action results (trajectory results) for EACH modal
    - Do NOT use "done" action here - "done" is only for final task completion
    - Do NOT just track it internally - it must be in action output
    - Do NOT skip this step - it's mandatory for task completion
    - Output this immediately after detecting each modal, before clicking Close
    - After reporting, continue to STEP 2 (close modal), then continue shooting for next modal
    - Repeat this for EACH of the 3 modals - each must have its own detection report in action results
    - Modal 1 detection → output report → close → continue
    - Modal 2 detection → output report → close → continue  
    - Modal 3 detection → output report → close → then done
    
    STEP 2 - CLOSE THE MODAL (REQUIRED - DO NOT SKIP):
    Immediately after reporting with extract action, you MUST use the "click" action to click the "Close" button.
    The Close button is the dark gray rectangular button at the bottom of the modal.
    
    IMPORTANT - HOW TO CLICK THE CLOSE BUTTON:
    - Use the "click" action (NOT JavaScript/evaluate action)
    - Look at the screenshot to find the dark gray "Close" button
    - The button is a dark gray rectangle at the bottom center of the modal, below the message text
    - It has white "Close" text inside it
    - Use click action and click directly on the button (use vision to find its coordinates)
    - After clicking, wait 2 seconds and take another screenshot to verify the modal closed
    - If the modal is still visible after clicking, the click may have missed - try clicking the button again
    - Make sure you're clicking the center of the button, not the edges
    - The modal will NOT close automatically - you MUST click it
    - Do NOT try to use JavaScript to close it - use the click action only
    
    TROUBLESHOOTING:
    - If click doesn't work, take another screenshot to see current state
    - Make sure you're clicking the actual button element, not just random coordinates
    - The button should be clearly visible in the screenshot before clicking
    - If the modal persists, try clicking the button again - sometimes it needs a second click
    - Verify the modal closed by taking a screenshot after clicking
    
    CRITICAL: You MUST close EVERY modal, including the third and final one!
    Even after detecting the third modal, you MUST still click "Close" to dismiss it.
    Do NOT skip closing any modal, including the last one.
    
    STEP 3 - CONTINUE FOR NEXT MODAL (DO NOT STOP YET):
    After closing the modal, check how many you've completed:
    
    - If this was modal #1: You have 2 more to go! Shoot 1-3 more times to trigger modal #2. DO NOT call "done"!
    - If this was modal #2: You have 1 more to go! Shoot 1-3 more times to trigger modal #3. DO NOT call "done"!
    - If this was modal #3: NOW you can complete the task (see TASK COMPLETE section below)
    
    CRITICAL: You must complete this cycle (detect → report → close) for EACH of the 3 modals separately.
    Do NOT try to detect all 3 at once. Do NOT skip clicking Close on any modal, including the third one.
    The third modal MUST also be closed after detection - do not leave it open!
    DO NOT call "done" until you have completed ALL 3 modals!
    
    TASK COMPLETE (ONLY AFTER ALL 3 ARE DETECTED AND CLOSED):
    ⚠️ DO NOT call "done" until you have completed ALL 3 detections and closures!
    
    Checklist before calling "done":
    ☐ Modal 1 detected, reported, and closed? → Continue, don't stop!
    ☐ Modal 2 detected, reported, and closed? → Continue, don't stop!
    ☐ Modal 3 detected, reported, and closed? → NOW you can call "done"
    
    Once you have detected, reported, and closed ALL 3 modals individually (including closing the third one), 
    THEN and ONLY THEN use the "done" action with this message:
    
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
    - DO NOT call "done" after 1 modal - you need ALL 3
    - DO NOT call "done" after 2 modals - you need ALL 3
    - ONLY call "done" after ALL 3 are complete
    """
    
    print(f"\n🤖 Starting harmful content detection monitor...")
    print("="*50)
    print("📋 Task: Detect all 3 types of harmful content")
    print("="*50)
    
    print("\n👁️  Vision mode enabled (CRITICAL for Canvas-based games)")
    print("⚡ Performance optimized: Using low detail vision for faster screenshot analysis")
    print("\nTask: Detect all 3 types of harmful content semantically:")
    print("  1. Violence/weapons (any content promoting violence)")
    print("  2. Drug promotion (any content encouraging drug use)")
    print("  3. Sexual/inappropriate (any inappropriate sexual content)")
    print("\nModal appears randomly after 1-3 shots, stays open until detected")
    print("⚠️  Note: Modal is rendered on Canvas - must use screenshots/vision, NOT DOM extraction")
    print("💡 Tip: Use 'click' action to close modals, NOT JavaScript\n")
    
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
    
    def detect_message_type_semantically(text):
        """
        Semantically detect which type of harmful content based on agent's analysis.
        Looks for semantic indicators in the agent's detection report, not exact message text.
        """
        text_lower = text.lower()
        
        # Look for semantic indicators in the agent's analysis/report
        # The agent should have analyzed the content and categorized it
        
        # Violence/Weapons indicators - look for semantic understanding
        violence_indicators = [
            "violence", "violent", "weapon", "weapons", "gun", "guns", 
            "harmful behavior", "promotes violence", "violence/weapons",
            "violates tos", "terms of service", "harmful content"
        ]
        violence_count = sum(1 for indicator in violence_indicators if indicator in text_lower)
        
        # Drug indicators - look for semantic understanding
        drug_indicators = [
            "drug", "drugs", "drug promotion", "substance", "substances",
            "harmful behavior", "promotes drug", "drug promotion",
            "violates tos", "terms of service", "harmful content"
        ]
        drug_count = sum(1 for indicator in drug_indicators if indicator in text_lower)
        
        # Sexual/Inappropriate indicators - look for semantic understanding
        sexual_indicators = [
            "sexual", "inappropriate", "photo", "photos", "nude", "explicit",
            "harmful behavior", "promotes sexual", "sexual/inappropriate",
            "violates tos", "terms of service", "harmful content"
        ]
        sexual_count = sum(1 for indicator in sexual_indicators if indicator in text_lower)
        
        # Check for explicit content type declarations in agent's report
        if "content type:" in text_lower:
            if "violence" in text_lower or "weapon" in text_lower:
                return 'violence'
            elif "drug" in text_lower:
                return 'drugs'
            elif "sexual" in text_lower or "inappropriate" in text_lower:
                return 'sexual'
        
        # Use counts to determine type (most indicators wins)
        # But require at least 2 indicators to avoid false positives
        if violence_count >= 2 and violence_count >= drug_count and violence_count >= sexual_count:
            return 'violence'
        elif drug_count >= 2 and drug_count >= sexual_count:
            return 'drugs'
        elif sexual_count >= 2:
            return 'sexual'
        
        # Fallback: if only one indicator found, use it
        if violence_count > 0 and drug_count == 0 and sexual_count == 0:
            return 'violence'
        elif drug_count > 0 and violence_count == 0 and sexual_count == 0:
            return 'drugs'
        elif sexual_count > 0 and violence_count == 0 and drug_count == 0:
            return 'sexual'
        
        return None
    
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
                    # Use semantic detection based on agent's analysis
                    msg_type = detect_message_type_semantically(output_str)
                    
                    # Map step index to screenshot index (screenshots are usually taken around the same step)
                    # Use step_idx as approximation, but clamp to valid range
                    screenshot_idx = None
                    if screenshot_paths:
                        screenshot_idx = min(step_idx, len(screenshot_paths) - 1)
                        detected_screenshot_indices.add(screenshot_idx)
                    
                    detections.append({
                        'step': step_idx + 1,
                        'type': msg_type,
                        'output': output_str,
                        'screenshot_idx': screenshot_idx
                    })
                    
                    if msg_type and not detected_types[msg_type]['detected']:
                        detected_types[msg_type]['detected'] = True
                        detected_types[msg_type]['screenshot_idx'] = screenshot_idx
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
                    msg_type = detect_message_type_semantically(result_str)
                    
                    if screenshot_paths:
                        screenshot_idx = min(step_idx, len(screenshot_paths) - 1)
                        detected_screenshot_indices.add(screenshot_idx)
                    
                    if msg_type and not detected_types[msg_type]['detected']:
                        detected_types[msg_type]['detected'] = True
                        detected_types[msg_type]['screenshot_idx'] = screenshot_idx if screenshot_paths else None
    
    # Also check final_result for any detections we might have missed
    if final_result:
        final_lower = final_result.lower()
        if "🚨" in final_result or "harmful content detected" in final_lower or "task complete" in final_lower:
            # Use semantic detection on final result
            msg_type = detect_message_type_semantically(final_result)
            if msg_type and not detected_types[msg_type]['detected']:
                detected_types[msg_type]['detected'] = True
    
    # Check extracted_content as well - use semantic analysis
    extracted_content = history.extracted_content()
    if extracted_content:
        for content in extracted_content:
            if content:
                content_str = str(content)
                # Use semantic detection on extracted content
                msg_type = detect_message_type_semantically(content_str)
                if msg_type and not detected_types[msg_type]['detected']:
                    detected_types[msg_type]['detected'] = True
    
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
                if dt.get('screenshot'):
                    print(f"    📸 Screenshot: {dt['screenshot']}")
                if dt.get('message'):
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
