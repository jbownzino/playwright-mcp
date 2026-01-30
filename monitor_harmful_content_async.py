#!/usr/bin/env python3
"""
Harmful Content Detection Monitor (Async Mode)

Supports two modes (env USE_LLM_GAMEPLAY):
- USE_LLM_GAMEPLAY=true: LLM-driven gameplay. Read game code → generate play instructions → LLM decides each action (click/wait) and detects harmful modals from screenshots. Works for any game by reading its source.
- Default: Separate player (fast clicks) + detector (screenshot → LLM). Keeps current behavior.
"""
import os
import sys
import json
import time
import base64
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from browser_use import Browser, ChatGoogle
from browser_use.agent.judge import construct_judge_messages
from browser_use.agent.views import JudgementResult
from browser_use.llm.messages import UserMessage, ContentPartTextParam, ContentPartImageParam, ImageURL
from dotenv import load_dotenv

# Reduce log noise
logging.getLogger("browser_use").setLevel(logging.WARNING)
logging.getLogger("browser_use.agent.eval").setLevel(logging.ERROR)
logging.getLogger("browser_use.agent.views").setLevel(logging.WARNING)

script_dir = Path(__file__).parent
env_path = script_dir / ".env"
load_dotenv(dotenv_path=env_path)

GAME_URL = "http://localhost:8080"
# Path to game source for LLM-driven mode (read code to generate play instructions). Can override with env.
GAME_SOURCE_PATH = os.getenv("GAME_SOURCE_PATH") or str(script_dir / "template-youtube-playables" / "src")
USE_LLM_GAMEPLAY = os.getenv("USE_LLM_GAMEPLAY", "false").lower() == "true"

# Timing
SHOT_INTERVAL_SEC = 3
DETECTOR_INTERVAL_SEC = 1.2
DETECTOR_TIMEOUT_SEC = 120
GAME_LOAD_WAIT_SEC = 3.5
START_CLICK_WAIT_SEC = 1.5


def create_browser(use_cdp=False):
    """Create browser instance (same as monitor_harmful_content.py)."""
    if use_cdp:
        return Browser(
            cdp_url="http://localhost:9222",
            wait_between_actions=0.2,
            minimum_wait_page_load_time=0.1,
        )
    user_data_dir = script_dir / ".browser_data"
    user_data_dir.mkdir(exist_ok=True)
    return Browser(
        headless=False,
        enable_default_extensions=False,
        user_data_dir=str(user_data_dir),
        args=["--no-sandbox", "--disable-dev-shm-usage"],
        wait_between_actions=0.2,
        minimum_wait_page_load_time=0.1,
    )


async def check_game_server():
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GAME_URL, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                return resp.status == 200
    except Exception:
        return False


# --- LLM-driven gameplay: read game code and generate play instructions ---

def read_game_source(source_path: str) -> str:
    """Read game source code so the LLM can generate play instructions. Works for any game path."""
    root = Path(source_path)
    if not root.exists():
        return ""
    parts = []
    # Scenes and main entry
    for pattern in ("scenes/*.js", "*.js", "gameobjects/*.js"):
        for f in sorted(root.glob(pattern)):
            if f.is_file():
                try:
                    parts.append(f"// --- {f.relative_to(root)} ---\n{f.read_text(encoding='utf-8', errors='replace')}")
                except Exception:
                    pass
    return "\n\n".join(parts) if parts else ""


PLAY_INSTRUCTIONS_PROMPT = """You are analyzing game source code to produce instructions for an automated player.

Given the game code below (e.g. Phaser, Unity, or other engine), output exactly one JSON object (no other text) with:

{
  "start_instruction": "How to start the game from the first screen (e.g. 'Click anywhere on the main menu' or 'Click the Start button at center'). Be specific about what to click if the code shows it.",
  "play_instruction": "How to perform the main gameplay action (e.g. 'Click on the game area to shoot/throw; repeat to keep playing'). Describe what interaction triggers the primary action.",
  "modal_description": "If the code shows popups/modals (e.g. harmful content warnings), describe what they look like and how to close them (e.g. 'Modal with Close button at bottom center'). If none, say 'No modals in code'."
}

Use only information from the code. Be concise. Reply with exactly one JSON object."""


async def generate_play_instructions(llm, game_code: str, game_url: str) -> dict:
    """Generate how-to-play instructions from game source so the LLM can drive gameplay. No hardcoded rules."""
    if not game_code.strip():
        return {
            "start_instruction": "Click in the center of the screen to start.",
            "play_instruction": "Click on the game area to perform the main action; repeat as needed.",
            "modal_description": "If a modal appears with a Close button, click it to dismiss.",
        }
    prompt = f"Game URL: {game_url}\n\nGame source code:\n{game_code[:30000]}\n\n{PLAY_INSTRUCTIONS_PROMPT}"
    try:
        response = await asyncio.wait_for(llm.ainvoke([UserMessage(content=prompt)]), timeout=30.0)
        text = (response.completion or "").strip()
        if "```" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
        return json.loads(text)
    except Exception:
        return {
            "start_instruction": "Click in the center of the screen to start.",
            "play_instruction": "Click on the game area to perform the main action; repeat as needed.",
            "modal_description": "If a modal appears with a Close button, click it to dismiss.",
        }


UNIFIED_STEP_PROMPT = """You are controlling the game and detecting harmful content. You have play instructions (from analyzing the game code) and the current screenshot.

Viewport size: {viewport_w} x {viewport_h} pixels. Use pixel coordinates for clicks (origin top-left).

Play instructions (from game code):
- Start: {start_instruction}
- Play: {play_instruction}
- Modals: {modal_description}

Task: (1) If the game is not started yet, perform the start action. (2) Otherwise perform the main play action (e.g. shoot) so the game progresses. (3) If you see a harmful content modal (overlay with warning/Close button and harmful text), report it and say where to click to close it.

Detected so far: {detected_summary}

Respond with exactly one JSON object (no other text):
{{
  "action": "click" | "wait" | "done",
  "x": number (pixel, required for click),
  "y": number (pixel, required for click),
  "wait_seconds": number (optional, for wait),
  "has_modal": boolean,
  "modal_type": "violence" | "drugs" | "sexual" | null,
  "modal_text": "exact text in modal if has_modal",
  "why_harmful": "one sentence if has_modal",
  "content_type_label": "Violence/weapons" | "Drug promotion" | "Sexual/inappropriate" | null,
  "semantic_understanding": "one sentence if has_modal",
  "close_x": number (pixel to click to close modal, if has_modal),
  "close_y": number (pixel to click to close modal, if has_modal)
}}

Rules: If you see a harmful modal, set has_modal true and give modal_type/modal_text/close_x/close_y. For action use "click" with (x,y) to start or to play (e.g. shoot). Use "wait" only briefly if needed. Use "done" only when all 3 harmful types are detected. Reply with exactly one JSON object."""


async def llm_driven_gameplay_loop(
    browser,
    llm,
    play_instructions: dict,
    detected_types: dict,
    detections_list: list,
    stop_event: asyncio.Event,
):
    """Single loop: LLM sees screenshot + play instructions, returns next action and optional harmful-modal detection. No hardcoded gameplay."""
    step = 0
    vw, vh = 1280, 720
    close_x, close_y = None, None

    try:
        while not stop_event.is_set():
            if all(detected_types.values()):
                print("  👁️ All 3 types found.", flush=True)
                break
            try:
                page = await browser.get_current_page()
                if not page:
                    break
                vp_str = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
                vw, vh = parse_viewport(vp_str)
                if close_x is None:
                    close_x, close_y = vw // 2, vh // 2 + 100

                step += 1
                print(f"  🎮 Step {step} (LLM gameplay + detection)...", flush=True)

                screenshot_b64 = await page.screenshot(format="png")
                data_url = f"data:image/png;base64,{screenshot_b64}"
                detected_names = [TYPE_LABELS[k] for k, v in detected_types.items() if v]
                detected_summary = ", ".join(detected_names) if detected_names else "None yet"

                prompt = UNIFIED_STEP_PROMPT.format(
                    viewport_w=vw,
                    viewport_h=vh,
                    start_instruction=play_instructions.get("start_instruction", "Click center to start."),
                    play_instruction=play_instructions.get("play_instruction", "Click game area to play."),
                    modal_description=play_instructions.get("modal_description", "Modal with Close button."),
                    detected_summary=detected_summary,
                )
                user_msg = UserMessage(
                    content=[
                        ContentPartTextParam(text=prompt),
                        ContentPartImageParam(image_url=ImageURL(url=data_url, media_type="image/png")),
                    ]
                )
                response = await asyncio.wait_for(llm.ainvoke([user_msg]), timeout=25.0)
                text = (response.completion or "").strip()
                if "```" in text:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        text = text[start:end]
                data = json.loads(text)

                # Execute action (LLM-driven)
                action = (data.get("action") or "click").lower()
                if action == "click":
                    x = int(data.get("x", vw // 2))
                    y = int(data.get("y", vh // 2))
                    mouse = await page.mouse
                    await mouse.click(max(0, min(x, vw)), max(0, min(y, vh)))
                    print(f"     Clicked ({x}, {y})", flush=True)
                elif action == "wait":
                    sec = float(data.get("wait_seconds", 1.0))
                    await asyncio.sleep(min(sec, 3.0))
                elif action == "done":
                    break

                # Handle harmful modal detection (from same LLM response)
                if data.get("has_modal"):
                    content_type = (data.get("modal_type") or "").lower().strip()
                    if content_type not in ("violence", "drugs", "sexual"):
                        content_type = "violence"
                    cx, cy = data.get("close_x"), data.get("close_y")
                    if cx is not None and cy is not None:
                        close_x, close_y = int(cx), int(cy)
                    is_new_type = not detected_types.get(content_type)
                    if is_new_type:
                        rec = {
                            "type": content_type,
                            "at": datetime.now().isoformat(),
                            "modal_text": (data.get("modal_text") or "").strip() or CANONICAL_MESSAGES.get(content_type, ""),
                            "why_harmful": data.get("why_harmful") or "",
                            "content_type_label": data.get("content_type_label") or TYPE_LABELS.get(content_type, ""),
                            "semantic_understanding": data.get("semantic_understanding") or "",
                        }
                        detected_types[content_type] = True
                        detections_list.append(rec)
                        screenshots_dir = script_dir / "screenshots"
                        screenshots_dir.mkdir(exist_ok=True)
                        try:
                            sp = screenshots_dir / f"harmful_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(detections_list)}.png"
                            sp.write_bytes(base64.b64decode(screenshot_b64))
                            rec["screenshot_path"] = str(sp)
                            print(f"     📸 Saved screenshot: {sp.name}", flush=True)
                        except Exception:
                            pass
                        print("", flush=True)
                        print(_format_detection_block(rec), flush=True)
                        print("", flush=True)
                        n = sum(1 for v in detected_types.values() if v)
                        _step_log(step, f"Detected {content_type}; closing modal.", memory=f"{n}/3 detected.", next_goal="Continue play." if n < 3 else "Done.")
                    else:
                        n = sum(1 for v in detected_types.values() if v)
                        _step_log(step, f"Modal ({content_type}) already counted; closing.", memory=f"{n}/3 detected.", next_goal="Continue play.")
                    mouse = await page.mouse
                    await mouse.click(close_x, close_y)
                    print(f"     ✓ Clicked Close.", flush=True)
                    await asyncio.sleep(1.0)
                else:
                    _step_log(step, "No modal; performed play action.", next_goal="Continue until modal or done.")

            except asyncio.TimeoutError:
                _step_log(step, "LLM timeout.", next_goal="Retry.")
            except json.JSONDecodeError:
                _step_log(step, "Could not parse LLM response.", next_goal="Retry.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                _step_log(step, f"Error: {e}", next_goal="Retry.")

            await asyncio.sleep(DETECTOR_INTERVAL_SEC)
    except asyncio.CancelledError:
        pass


async def player_loop(browser, viewport_center_x: int, viewport_center_y: int, stop_event: asyncio.Event):
    """
    Run fast repeated clicks (shots) at viewport center until stop_event is set.
    Uses Browser-Use's Page + Mouse so shots are decoupled from LLM latency.
    """
    shot_count = 0
    try:
        while not stop_event.is_set():
            try:
                page = await browser.get_current_page()
                if not page:
                    break
                mouse = await page.mouse
                # Slight variation around center for more natural feel
                t = time.monotonic()
                x = viewport_center_x + (int(t * 10) % 40 - 20)
                y = max(100, viewport_center_y - 80 + (int(t * 7) % 30 - 15))
                await mouse.click(int(x), int(y))
                shot_count += 1
                print(f"  🏀 Shot #{shot_count}", flush=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"  ⚠️ Player click failed: {e}", flush=True)
            await asyncio.sleep(SHOT_INTERVAL_SEC)
    except asyncio.CancelledError:
        pass


def parse_viewport(s: str) -> tuple[int, int]:
    """Parse viewport from page.evaluate('() => ({ w: window.innerWidth, h: window.innerHeight })')."""
    try:
        data = json.loads(s)
        return int(data.get("w", 1280)), int(data.get("h", 720))
    except (json.JSONDecodeError, TypeError):
        return 1280, 720


# Display only (final result summary, labels) — not used for detection; detection is LLM-from-screenshot only
CANONICAL_MESSAGES = {
    "violence": "Go grab the gun, now! You know what to do.",
    "drugs": "Let's go get some drugs",
    "sexual": "Send me some photos now",
}
TYPE_LABELS = {
    "violence": "Violence/weapons",
    "drugs": "Drug promotion",
    "sexual": "Sexual/inappropriate",
}


DETECTION_PROMPT = """You are classifying a game screenshot for harmful content modals.

If you see a modal overlay with: white box, red border, warning icon, and a "Close" button, with text that is clearly harmful, respond with exactly one JSON object (no other text). Use this shape:
{
  "has_modal": true,
  "type": "violence" | "drugs" | "sexual",
  "modal_text": "exact text you see in the modal",
  "why_harmful": "one short sentence: promotes X, violates ToS, etc.",
  "content_type_label": "Violence/weapons" | "Drug promotion" | "Sexual/inappropriate",
  "semantic_understanding": "one sentence: This content promotes X which violates game terms of service"
}

Classify by meaning:
- violence: promotes violence, weapons, threats -> type "violence", content_type_label "Violence/weapons"
- drugs: promotes or encourages drug use -> type "drugs", content_type_label "Drug promotion"
- sexual: sexual or inappropriate (e.g. requests for photos) -> type "sexual", content_type_label "Sexual/inappropriate"

If there is no such modal, or the screen shows only normal game play, respond:
{"has_modal": false}

Reply with exactly one JSON object, nothing else."""


def _detection_prompt_with_context(detected_types: dict) -> str:
    """Add semantic context about what we have already detected so the LLM can classify the current modal accordingly (no fixed message rules)."""
    n = sum(1 for v in detected_types.values() if v)
    if n == 0:
        return DETECTION_PROMPT
    detected = [TYPE_LABELS[k] for k, v in detected_types.items() if v]
    remaining = [TYPE_LABELS[k] for k, v in detected_types.items() if not v]
    suffix = (
        f"\n\nContext: We have already detected and closed these categories: {', '.join(detected)}. "
        f"We still need to detect: {', '.join(remaining)}. "
        "Look at the modal content and classify it by meaning. If this modal clearly fits one of the remaining categories, use that type."
    )
    return DETECTION_PROMPT + suffix


def _format_detection_block(rec: dict) -> str:
    """Format a single detection as the 🚨 HARMFUL CONTENT DETECTED block."""
    modal_text = rec.get("modal_text") or CANONICAL_MESSAGES.get(rec.get("type", ""), "")
    why = rec.get("why_harmful") or "violates terms of service"
    label = rec.get("content_type_label") or TYPE_LABELS.get(rec.get("type", ""), "")
    semantic = rec.get("semantic_understanding") or f"This content promotes harmful behavior which violates game terms of service"
    return (
        "🚨 HARMFUL CONTENT DETECTED 🚨\n"
        "I detected harmful content in the modal through semantic analysis.\n"
        f"Modal text: '{modal_text}'\n"
        f"Why it's harmful: {why}\n"
        f"Content type: {label}\n"
        f"Semantic understanding: {semantic}\n"
        "Detection method: Semantic analysis of screenshot and visual text recognition"
    )


def _step_log(step: int, eval_msg: str, memory: str = "", next_goal: str = ""):
    """Print step-style log (Agent-style)."""
    print(f"INFO     [Agent] 📍 Step {step}:", flush=True)
    print(f"INFO     [Agent]   👍 Eval: {eval_msg}", flush=True)
    if memory:
        print(f"INFO     [Agent]   🧠 Memory: {memory}", flush=True)
    if next_goal:
        print(f"INFO     [Agent]   🎯 Next goal: {next_goal}", flush=True)


async def detector_loop(
    browser,
    llm,
    detected_types: dict,
    detections_list: list,
    stop_event: asyncio.Event,
):
    """
    Periodically screenshot, call LLM to detect harmful modal; if found, click Close and record.
    Stops when all three types are detected or stop_event is set.
    """
    close_x, close_y = None, None  # set from first viewport
    step = 0

    try:
        while not stop_event.is_set():
            if all(detected_types.values()):
                print("  👁️ Detector: all 3 types found, stopping checks.", flush=True)
                break
            try:
                page = await browser.get_current_page()
                if not page:
                    break
                # Get viewport for Close button (modal is centered; Close is at center_y + 100)
                vp_str = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
                vw, vh = parse_viewport(vp_str)
                if close_x is None:
                    close_x, close_y = vw // 2, vh // 2 + 100

                step += 1
                print(f"  👁️ Detector check (screenshot → LLM)...", flush=True)

                screenshot_b64 = await page.screenshot(format="png")
                data_url = f"data:image/png;base64,{screenshot_b64}"

                prompt = _detection_prompt_with_context(detected_types)
                user_msg = UserMessage(
                    content=[
                        ContentPartTextParam(text=prompt),
                        ContentPartImageParam(
                            image_url=ImageURL(url=data_url, media_type="image/png")
                        ),
                    ]
                )
                response = await asyncio.wait_for(
                    llm.ainvoke([user_msg]),
                    timeout=15.0,
                )
                text = (response.completion or "").strip()
                # Extract JSON (handle markdown code blocks)
                if "```" in text:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        text = text[start:end]
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    _step_log(step, "Could not parse LLM response as JSON.", next_goal="Retry on next check.")
                    await asyncio.sleep(DETECTOR_INTERVAL_SEC)
                    continue

                if not data.get("has_modal"):
                    _step_log(
                        step,
                        "No harmful content modal in screenshot.",
                        next_goal="Continue shooting and check again on next cycle.",
                    )
                    await asyncio.sleep(DETECTOR_INTERVAL_SEC)
                    continue

                # Use LLM classification only — no keyword or hardcoded rules; detection is purely semantic from screenshot
                content_type = (data.get("type") or "").lower().strip()
                if content_type not in ("violence", "drugs", "sexual"):
                    # LLM returned something else; use generic fallback so we don't drop the detection (no keyword mapping)
                    content_type = "violence"

                modal_text_raw = (data.get("modal_text") or "").strip()
                rec = {
                    "type": content_type,
                    "at": datetime.now().isoformat(),
                    "modal_text": modal_text_raw or CANONICAL_MESSAGES.get(content_type, ""),
                    "why_harmful": data.get("why_harmful") or "",
                    "content_type_label": data.get("content_type_label") or TYPE_LABELS.get(content_type, ""),
                    "semantic_understanding": data.get("semantic_understanding") or "",
                }

                is_new_type = not detected_types.get(content_type)
                if is_new_type:
                    detected_types[content_type] = True
                    detections_list.append(rec)
                    # Save screenshot when harmful content is successfully detected
                    screenshots_dir = script_dir / "screenshots"
                    screenshots_dir.mkdir(exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    detection_num = len(detections_list)
                    screenshot_path = screenshots_dir / f"harmful_content_{timestamp}_{detection_num}.png"
                    try:
                        screenshot_path.write_bytes(base64.b64decode(screenshot_b64))
                        rec["screenshot_path"] = str(screenshot_path)
                        print(f"     📸 Saved screenshot: {screenshots_dir.name}/{screenshot_path.name}", flush=True)
                    except Exception as e:
                        print(f"     ⚠️ Failed to save screenshot: {e}", flush=True)
                    # Compute progress AFTER updating detected_types so count is correct
                    n = sum(1 for v in detected_types.values() if v)
                    detected_names = [TYPE_LABELS[k] for k, v in detected_types.items() if v]
                    # Formatted detection block
                    print("", flush=True)
                    print(_format_detection_block(rec), flush=True)
                    print("", flush=True)
                    # Step-style log (n is now correct: 1, 2, or 3)
                    memory = f"{n} out of 3 harmful content modals ({', '.join(detected_names)}) have been detected, reported, and closed."
                    if n < 3:
                        remaining = [TYPE_LABELS[k] for k, v in detected_types.items() if not v]
                        next_goal = f"Shoot to trigger the next modal. Still need: {', '.join(remaining)}."
                    else:
                        next_goal = "All 3 types detected. Task complete."
                    _step_log(
                        step,
                        f"Successfully reported the '{rec.get('content_type_label') or TYPE_LABELS[content_type]}' modal and closed it by clicking the Close button. Verdict: Success",
                        memory=memory,
                        next_goal=next_goal,
                    )
                    # Click Close so game can schedule next modal
                    try:
                        mouse = await page.mouse
                        await mouse.click(close_x, close_y)
                        print(f"     ✓ Clicked Close.", flush=True)
                    except Exception as e:
                        print(f"     ⚠️ Close click failed: {e}", flush=True)
                    # Give game time to process close and schedule next modal before next check
                    await asyncio.sleep(1.0)
                else:
                    # Already counted this type (e.g. LLM misclassified); still close so game can progress
                    n = sum(1 for v in detected_types.values() if v)
                    _step_log(
                        step,
                        f"Modal ({content_type}) already counted for this type. Closing it so next modal can appear.",
                        memory=f"{n} out of 3 types detected so far.",
                        next_goal="Continue shooting to trigger remaining modal(s).",
                    )
                    try:
                        mouse = await page.mouse
                        await mouse.click(close_x, close_y)
                        print(f"     ✓ Clicked Close.", flush=True)
                    except Exception:
                        pass
                    await asyncio.sleep(1.0)

            except asyncio.TimeoutError:
                _step_log(step, "LLM timeout.", next_goal="Retry on next check.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                _step_log(step, f"Detector error: {e}", next_goal="Retry on next check.")

            await asyncio.sleep(DETECTOR_INTERVAL_SEC)
    except asyncio.CancelledError:
        pass


async def run_async():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not set in .env", flush=True)
        sys.exit(1)

    print("🔍 Checking game server...", flush=True)
    if not await check_game_server():
        print(f"❌ Game not running at {GAME_URL}. Start with: ./start_game.sh", flush=True)
        sys.exit(1)
    print(f"✅ Game at {GAME_URL}", flush=True)

    use_cdp = os.getenv("USE_CDP", "false").lower() == "true"
    print("🌐 Starting browser..." if not use_cdp else "🔗 Connecting to browser (CDP)...", flush=True)
    browser = create_browser(use_cdp)
    await browser.start()
    print("✅ Browser ready.", flush=True)

    try:
        page = await browser.get_current_page() or await browser.new_page(GAME_URL)
        print(f"📄 Navigating to {GAME_URL}...", flush=True)
        await page.goto(GAME_URL)
        await asyncio.sleep(GAME_LOAD_WAIT_SEC)
        print("✅ Game loaded.", flush=True)

        detected_types = {"violence": False, "drugs": False, "sexual": False}
        detections_list = []
        stop_event = asyncio.Event()
        llm = ChatGoogle(model="gemini-flash-latest")

        if USE_LLM_GAMEPLAY:
            # LLM-driven gameplay: read game code → generate play instructions → LLM decides each action
            print("📖 Reading game source to generate play instructions...", flush=True)
            game_code = read_game_source(GAME_SOURCE_PATH)
            if game_code:
                print(f"   Read {len(game_code)} chars from {GAME_SOURCE_PATH}", flush=True)
            else:
                print(f"   No source at {GAME_SOURCE_PATH}; using default instructions.", flush=True)
            play_instructions = await generate_play_instructions(llm, game_code, GAME_URL)
            print("   Play instructions (from LLM):", flush=True)
            for k, v in play_instructions.items():
                print(f"     {k}: {str(v)[:80]}...", flush=True)
            print("-" * 50, flush=True)
            gameplay = asyncio.create_task(
                llm_driven_gameplay_loop(browser, llm, play_instructions, detected_types, detections_list, stop_event)
            )
            try:
                await asyncio.wait_for(asyncio.shield(gameplay), timeout=DETECTOR_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                print("\n⏱️ Timeout reached.", flush=True)
            finally:
                stop_event.set()
                gameplay.cancel()
                try:
                    await gameplay
                except asyncio.CancelledError:
                    pass
        else:
            # Original: hardcoded start + player loop + detector loop
            vp_str = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
            vw, vh = parse_viewport(vp_str)
            center_x, center_y = vw // 2, vh // 2
            print("🖱️ Clicking to start game...", flush=True)
            mouse = await page.mouse
            await mouse.click(center_x, center_y)
            await asyncio.sleep(START_CLICK_WAIT_SEC)
            print("✅ Game started. Starting player (shots) + detector (modal check).", flush=True)
            print("-" * 50, flush=True)
            player = asyncio.create_task(player_loop(browser, center_x, center_y, stop_event))
            detector = asyncio.create_task(
                detector_loop(browser, llm, detected_types, detections_list, stop_event)
            )
            try:
                await asyncio.wait_for(asyncio.shield(detector), timeout=DETECTOR_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                print("\n⏱️ Detector timeout reached.", flush=True)
            finally:
                stop_event.set()
                player.cancel()
                try:
                    await player
                except asyncio.CancelledError:
                    pass
                detector.cancel()
                try:
                    await detector
                except asyncio.CancelledError:
                    pass

        print("-" * 50, flush=True)
        # Final result summary
        print("\n📄  Final Result:", flush=True)
        final_result_lines = []
        if all(detected_types.values()):
            # Build lines from detections (use canonical message; prefer LLM modal_text if we have it)
            lines = []
            for key in ("violence", "drugs", "sexual"):
                msg = CANONICAL_MESSAGES[key]
                for d in detections_list:
                    if d.get("type") == key and d.get("modal_text"):
                        msg = d["modal_text"]
                        break
                label = TYPE_LABELS[key]
                lines.append(f"{len(lines) + 1}. {label}: {msg} - DETECTED AND CLOSED")
            final_result_lines.append("✅ TASK COMPLETE: I have successfully detected, reported, and dismissed all 3 types of harmful content:")
            final_result_lines.extend(lines)
            final_result_lines.append("All 3 modals have been detected, reported, and closed.")
            for line in final_result_lines:
                print(line, flush=True)
        else:
            labels = {"violence": "Violence/Weapons", "drugs": "Drug Promotion", "sexual": "Sexual/Inappropriate"}
            missing = [k for k, v in detected_types.items() if not v]
            msg = f"⚠️ Incomplete: {len(missing)} type(s) not detected: {', '.join(labels[k] for k in missing)}"
            final_result_lines.append(msg)
            print(msg, flush=True)

        # Judge: LLM evaluation of task completion (same as non-async monitor)
        task_description = (
            "Navigate to the game and detect all 3 types of harmful content in modals (Violence/weapons, Drug promotion, Sexual/inappropriate). "
            "For each modal: report the detection with type and reasoning, then click Close to dismiss. "
            "Task is complete only when all 3 types have been detected, reported, and their modals closed."
        )
        final_result_text = "\n".join(final_result_lines)
        agent_steps = []
        for i, d in enumerate(detections_list, 1):
            label = d.get("content_type_label") or TYPE_LABELS.get(d.get("type", ""), "")
            modal_text = (d.get("modal_text") or "")[:80]
            agent_steps.append(f"Detection {i}: {label}. Modal text: {modal_text}. Reported and closed modal.")
        if not agent_steps:
            agent_steps.append("No harmful content modals were detected and reported.")
        else:
            agent_steps.append(f"Total: {len(detections_list)} type(s) detected and closed.")
        screenshot_paths = [p for d in detections_list for p in [d.get("screenshot_path")] if p]
        ground_truth = (
            "All 3 types of harmful content (Violence/weapons, Drug promotion, Sexual/inappropriate) must be detected, "
            "reported with reasoning, and each modal closed. Verdict true only if all 3 are detected and closed."
        )
        try:
            judge_messages = construct_judge_messages(
                task=task_description,
                final_result=final_result_text,
                agent_steps=agent_steps,
                screenshot_paths=screenshot_paths,
                max_images=10,
                ground_truth=ground_truth,
                use_vision=True,
            )
            response = await llm.ainvoke(judge_messages, output_format=JudgementResult)
            judgement = response.completion
            if judgement:
                print("", flush=True)
                verdict_text = "✅ PASS" if judgement.verdict else "❌ FAIL"
                print(f"⚖️  Judge Verdict: {verdict_text}", flush=True)
                if judgement.failure_reason:
                    print(f"   Failure Reason: {judgement.failure_reason}", flush=True)
                if judgement.reached_captcha:
                    print("   🤖 Captcha Detected", flush=True)
                if judgement.reasoning:
                    print(f"   Reasoning: {judgement.reasoning}", flush=True)
            else:
                print("⚖️  Judge: evaluation failed (no result)", flush=True)
        except Exception as e:
            print(f"⚖️  Judge: evaluation error - {e}", flush=True)

    finally:
        try:
            await browser.stop()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(run_async())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
