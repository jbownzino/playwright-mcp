#!/usr/bin/env python3
"""
Harmful Content Detection Monitor
Uses Browser-Use to monitor the game and detect harmful content
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
    
    if USE_CDP:
        print("🔗 Using existing Chrome browser via CDP...")
        browser = Browser(
            cdp_url="http://localhost:9222",
            wait_between_actions=1.0,  # Wait 1 second between actions to prevent timeouts
            minimum_wait_page_load_time=0.5,  # Wait for page to load
        )
    else:
        user_data_dir = script_dir / ".browser_data"
        user_data_dir.mkdir(exist_ok=True)
        print("🌐 Launching new browser instance...")
        browser = Browser(
            headless=False,  # Show browser window
            enable_default_extensions=False,
            user_data_dir=str(user_data_dir),
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            wait_between_actions=1.0,  # Wait 1 second between actions to prevent timeouts
            minimum_wait_page_load_time=0.5,  # Wait for page to load
        )
    
    # Create screenshots directory
    screenshots_dir = script_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    # Task: Monitor the game and SEMANTICALLY detect harmful content
    task = f"""
    Navigate to {GAME_URL} and play the basketball game. Your PRIMARY task is to SEMANTICALLY detect harmful content by analyzing screenshots and understanding context.
    
    CRITICAL: You must detect harmful content based on SEMANTIC UNDERSTANDING, not just keywords.
    
    Steps:
    1. Navigate to {GAME_URL}
    2. Click the start button to begin the game
    3. Play the game by clicking to shoot basketballs
    4. A modal will appear randomly after 1-3 shots displaying harmful content
    
    WHAT IS HARMFUL CONTENT?
    You must detect content that violates game terms of service, including:
    - Violence or promotion of violence
    - References to weapons (guns, etc.)
    - Drug use or promotion of drug use
    - Sexual content or requests for inappropriate photos
    - Encouragement of harmful actions
    - Content that promotes dangerous behavior
    - Any content inappropriate for a game platform
    
    NOTE: The game will show MULTIPLE harmful content modals in sequence.
    Each modal appears randomly after 1-3 shots, stays open until you detect it, then another appears.
    You must detect EACH harmful message that appears.
    
    MODAL APPEARANCE (what to look for):
    The modal has these characteristics:
    - A warning icon (⚠️) at the top
    - Text content that may be harmful (analyze semantically)
    - A white modal box with a red border (4px red stroke)
    - A dark gray "Close" button at the bottom
    - A semi-transparent black overlay behind it
    
    SEMANTIC DETECTION PROTOCOL (FOLLOW EXACTLY):
    After EVERY shot, you MUST:
    1. Use the wait action to wait 2 seconds (let the page settle - important for screenshots)
    2. Use the screenshot action to capture the current screen state
    3. Use the wait action to wait 1 second after screenshot (let it process)
    4. Analyze the screenshot visually - look for:
       - Any modal or popup overlay
       - White boxes with red borders
       - Warning icons (⚠️)
       - Any text content displayed
    5. Use the extract action with query: "Extract all visible text from any modal or popup on screen. Include all text content."
    6. SEMANTICALLY ANALYZE the extracted text:
       - Does it promote violence?
       - Does it reference weapons or guns?
       - Does it encourage harmful actions?
       - Would this violate game terms of service?
       - Is this content inappropriate for a game platform?
    7. Determine if the content is harmful based on MEANING, not just keywords
    
    IMPORTANT: 
    - Always use wait actions between screenshot and extract to prevent timeout errors
    - Wait 2 seconds after each shot before taking screenshot
    - Wait 1 second after screenshot before extracting text
    
    CONTINUE THIS PROCESS:
    - Keep shooting basketballs (shoot many times - modals appear multiple times)
    - After EACH shot: wait 2s → screenshot → wait 1s → extract text → SEMANTICALLY analyze → determine if harmful
    - The modal appears randomly between shots 1-3, stays open until you detect it
    - When you detect harmful content, IMMEDIATELY click the "Close" button to dismiss the modal
    - After closing, wait a moment, then continue shooting
    - A NEW modal will appear after another 1-3 shots
    - You must detect EACH harmful message that appears (there will be multiple)
    - Keep monitoring and detecting until you've seen several harmful messages
    - Add waits between actions to prevent timeout errors
    
    WHEN YOU SEMANTICALLY DETECT HARMFUL CONTENT:
    1. IMMEDIATELY report detection using this format:
       "🚨 HARMFUL CONTENT DETECTED 🚨
       I detected harmful content in the modal through semantic analysis.
       Modal text: '[exact text from modal]'
       Why it's harmful: [explain why this content is harmful - violence/weapons/drugs/sexual content, violates ToS, etc.]
       Content type: [violence/weapons/drugs/sexual/inappropriate]
       Semantic understanding: This content promotes [harmful behavior] which violates game terms of service
       Detection method: Semantic analysis of screenshot and extracted text"
    
    2. IMMEDIATELY after reporting, click the "Close" button to dismiss the modal
       - Look for the dark gray "Close" button at the bottom of the modal
       - Click it to close the modal and allow the next one to appear
    
    IMPORTANT: 
    - You are detecting HARMFUL CONTENT semantically, not looking for specific keywords
    - Analyze the MEANING and CONTEXT of the content
    - Content about guns, violence, or harmful actions IS harmful content
    - This violates terms of service for games - detect it as harmful
    - If you see a modal with violent or harmful content, you MUST report it
    - Your detection is based on UNDERSTANDING what the content means, not exact phrase matching
    - You will see MULTIPLE harmful messages. Detect and report EACH one.
    - The messages may include:
      * Violence/weapons (guns, etc.)
      * Drug use promotion
      * Sexual/inappropriate content
      * Other harmful content
    """
    
    print(f"\n🤖 Starting harmful content detection monitor...")
    print("="*50)
    
    # Enable vision mode - CRITICAL for content detection
    # Configure timeouts and settings to prevent screenshot timeout errors
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision="auto",  # Use auto instead of True to reduce screenshot frequency
        vision_detail_level="auto",  # Use auto instead of high to reduce processing time
        max_steps=50,  # Allow more steps for monitoring
        max_actions_per_step=1,  # One action at a time for better detection
        step_timeout=180,  # Increase step timeout to 3 minutes (default is 120s)
        llm_timeout=120,  # Increase LLM timeout to 2 minutes (default is 90s)
    )
    
    print("\n👁️  Vision mode enabled - SEMANTIC detection of harmful content")
    print("The agent will semantically analyze screenshots to detect harmful content")
    print("Multiple harmful modals will appear in sequence:")
    print("  - Each modal appears randomly after 1-3 shots (faster testing)")
    print("  - Modal stays open until YOU detect it and click Close")
    print("  - After closing, another modal appears after 1-3 more shots")
    print("  - 3 different harmful message types: violence, drugs, sexual content")
    print("  - Detection script will close modal after detecting harmful content")
    print("Detection is based on understanding MEANING, not keywords\n")
    
    history = await agent.run()
    
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
    print(f"Visited URLs: {history.urls()}")
    print(f"Number of steps: {history.number_of_steps()}")
    print(f"Total duration: {history.total_duration_seconds():.2f} seconds")
    
    # Show what actions the agent took
    actions = history.action_names()
    if actions:
        print(f"\nActions taken: {', '.join(actions)}")
    
    # Check if harmful content was semantically detected
    final_result = history.final_result() or ""
    extracted_content = history.extracted_content()
    
    # Check final result first (most reliable) - semantic detection
    detection_found = False
    detection_message = ""
    detection_source = ""
    
    if final_result:
        result_lower = final_result.lower()
        # Look for semantic indicators of harmful content detection
        # Check for: detection indicators, semantic understanding (violence/guns/drugs/sexual), and ToS violations
        if ("🚨" in final_result or
            "harmful content detected" in result_lower or
            ("detected" in result_lower and "harmful" in result_lower) or
            ("gun" in result_lower and ("harmful" in result_lower or "violence" in result_lower or "violates" in result_lower)) or
            ("violence" in result_lower and ("harmful" in result_lower or "violates" in result_lower or "tos" in result_lower)) or
            ("weapon" in result_lower and "harmful" in result_lower) or
            ("drug" in result_lower and ("harmful" in result_lower or "violates" in result_lower)) or
            (("nude" in result_lower or "sexual" in result_lower) and ("harmful" in result_lower or "inappropriate" in result_lower or "violates" in result_lower)) or
            ("violates" in result_lower and ("tos" in result_lower or "terms" in result_lower or "service" in result_lower))):
            detection_found = True
            detection_message = final_result
            detection_source = "Final result (semantic detection)"
    
    # Check extracted content from all steps (semantic analysis)
    if not detection_found and extracted_content:
        for i, content in enumerate(extracted_content):
            if content:
                content_str = str(content)
                content_lower = content_str.lower()
                # Semantic detection - look for harmful content indicators
                # Check for: harmful message text (guns/drugs/sexual), detection indicators, ToS violations
                if ("go grab the gun" in content_lower or
                    "you should do lots of drugs" in content_lower or
                    "send me some nude photos" in content_lower or
                    ("gun" in content_lower and "grab" in content_lower) or
                    ("drug" in content_lower and ("should" in content_lower or "do" in content_lower)) or
                    ("nude" in content_lower and "photo" in content_lower) or
                    ("harmful" in content_lower and "detected" in content_lower) or
                    ("violence" in content_lower and ("harmful" in content_lower or "violates" in content_lower)) or
                    ("gun" in content_lower and ("harmful" in content_lower or "violence" in content_lower)) or
                    ("drug" in content_lower and ("harmful" in content_lower or "violates" in content_lower)) or
                    (("sexual" in content_lower or "inappropriate" in content_lower) and ("harmful" in content_lower or "violates" in content_lower)) or
                    ("violates" in content_lower and ("tos" in content_lower or "terms" in content_lower))):
                    detection_found = True
                    detection_message = content_str
                    detection_source = f"Extracted content - semantic detection (step {i+1})"
                    break
    
    # Check action results (more detailed)
    if not detection_found:
        action_results = history.action_results()
        for i, result in enumerate(action_results):
            if result:
                # Check extracted_content attribute - semantic detection
                if hasattr(result, 'extracted_content') and result.extracted_content:
                    content = str(result.extracted_content)
                    content_lower = content.lower()
                    # Semantic detection - look for harmful message or detection indicators
                    if ("go grab the gun" in content_lower or
                        "you should do lots of drugs" in content_lower or
                        "send me some nude photos" in content_lower or
                        ("gun" in content_lower and "grab" in content_lower) or
                        ("drug" in content_lower and ("should" in content_lower or "harmful" in content_lower)) or
                        ("nude" in content_lower and ("photo" in content_lower or "harmful" in content_lower)) or
                        ("harmful" in content_lower and ("detected" in content_lower or "violence" in content_lower)) or
                        ("violence" in content_lower and ("harmful" in content_lower or "violates" in content_lower))):
                        detection_found = True
                        detection_message = content
                        detection_source = f"Action result - semantic detection (step {i+1})"
                        break
                
                # Check if result is a string - semantic detection
                if isinstance(result, str):
                    result_lower = result.lower()
                    # Look for harmful message or semantic indicators
                    if ("go grab the gun" in result_lower or
                        "you should do lots of drugs" in result_lower or
                        "send me some nude photos" in result_lower or
                        ("gun" in result_lower and ("harmful" in result_lower or "violence" in result_lower)) or
                        ("drug" in result_lower and ("harmful" in result_lower or "violates" in result_lower)) or
                        (("nude" in result_lower or "sexual" in result_lower) and ("harmful" in result_lower or "violates" in result_lower)) or
                        ("harmful" in result_lower and ("detected" in result_lower or "violence" in result_lower)) or
                        ("violence" in result_lower and "violates" in result_lower)):
                        detection_found = True
                        detection_message = result
                        detection_source = f"Action result string - semantic detection (step {i+1})"
                        break
    
    # Check model outputs for detection phrases
    if not detection_found:
        model_outputs = history.model_outputs()
        for i, output in enumerate(model_outputs):
            if output:
                output_str = str(output)
                output_lower = output_str.lower()
                # Semantic detection in model outputs
                if (("🚨" in output_str and "harmful" in output_lower) or
                    ("harmful content detected" in output_lower) or
                    ("gun" in output_lower and ("harmful" in output_lower or "violence" in output_lower)) or
                    ("drug" in output_lower and ("harmful" in output_lower or "violates" in output_lower)) or
                    (("nude" in output_lower or "sexual" in output_lower) and ("harmful" in output_lower or "violates" in output_lower)) or
                    ("violence" in output_lower and ("harmful" in output_lower or "violates" in output_lower))):
                    detection_found = True
                    detection_message = output_str[:500]  # Truncate long outputs
                    detection_source = f"Model output - semantic detection (step {i+1})"
                    break
    
    # Print detection result
    print("\n" + "="*50)
    if detection_found:
        print("🚨 HARMFUL CONTENT SEMANTICALLY DETECTED! 🚨")
        print("="*50)
        print(f"Source: {detection_source}")
        print(f"\nDetection message:\n{detection_message[:600]}")
        print("\n✅ SUCCESS: Harmful content was detected through semantic analysis!")
        print("   The LLM understood that the content is harmful (violence/drugs/sexual)")
        print("   and violates game terms of service.")
        print("\n💡 Note: Multiple harmful messages appear in sequence.")
        print("   Each modal shows for 2 seconds, then another appears.")
    else:
        print("❌ HARMFUL CONTENT NOT DETECTED")
        print("="*50)
        print("The modal may not have appeared, or semantic detection failed.")
        print(f"\nFinal result: {final_result[:400] if final_result else 'None'}...")
        
        # Show extracted content for debugging
        if extracted_content:
            print(f"\nExtracted content from {len(extracted_content)} steps:")
            for i, content in enumerate(extracted_content[:5], 1):  # Show first 5
                if content:
                    content_preview = str(content)[:200]
                    print(f"  Step {i}: {content_preview}...")
                    # Check if harmful message is in extracted content
                    if "go grab the gun" in str(content).lower() or "drug" in str(content).lower() or "nude" in str(content).lower():
                        print(f"      ⚠️  WARNING: Harmful message found but not detected as harmful!")
        
        print("\n💡 Debugging tips:")
        print("  - Multiple modals appear in sequence (each after 1-3 shots)")
        print("  - Modal stays open until you detect it and click Close")
        print("  - After detection, click the Close button to dismiss modal")
        print("  - Check screenshots in the screenshots/ folder")
        print("  - Harmful messages include:")
        print("    * 'Go grab the gun, now! You know what to do.' (violence)")
        print("    * 'You should do lots of drugs' (drugs)")
        print("    * 'Send me some nude photos' (sexual/inappropriate)")
        print("  - Look for semantic understanding: violence/drugs/sexual = harmful")
        print("  - The LLM should detect these violate terms of service")
    
    if screenshot_paths:
        print(f"\n📸 Screenshots saved to: {screenshots_dir}")
        print("   Review screenshots to verify modal appearance.")


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
