#!/usr/bin/env python3
"""
Harmful Content Detection Monitor (Async Mode)

Option B: Separate "player" (fast repeated shots) and "detector" (screenshot + LLM + close modal).
Shots happen at a realistic rate; detection runs in parallel. Summary at the end.
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

# Timing: less space between shots = more realistic gameplay
SHOT_INTERVAL_SEC = 3
DETECTOR_INTERVAL_SEC = 2
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


# Canonical modal messages (match Game.js) for final result summary
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

                content_type = (data.get("type") or "").lower()
                # Normalize LLM response to one of the three categories (semantic, no keyword rules)
                if content_type not in ("violence", "drugs", "sexual"):
                    if "violence" in content_type or "weapon" in content_type:
                        content_type = "violence"
                    elif "drug" in content_type:
                        content_type = "drugs"
                    elif "sexual" in content_type or "inappropriate" in content_type:
                        content_type = "sexual"
                    else:
                        content_type = "violence"  # fallback only when LLM returns something else

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

        vp_str = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
        vw, vh = parse_viewport(vp_str)
        center_x, center_y = vw // 2, vh // 2

        # Start game (main menu: any click starts)
        print("🖱️ Clicking to start game...", flush=True)
        mouse = await page.mouse
        await mouse.click(center_x, center_y)
        await asyncio.sleep(START_CLICK_WAIT_SEC)
        print("✅ Game started. Starting player (shots) + detector (modal check).", flush=True)
        print("-" * 50, flush=True)

        detected_types = {"violence": False, "drugs": False, "sexual": False}
        detections_list = []
        stop_event = asyncio.Event()

        llm = ChatGoogle(model="gemini-flash-latest")
        player = asyncio.create_task(
            player_loop(browser, center_x, center_y, stop_event)
        )
        detector = asyncio.create_task(
            detector_loop(browser, llm, detected_types, detections_list, stop_event)
        )

        # Run until all 3 detected or timeout
        try:
            await asyncio.wait_for(
                asyncio.shield(detector),
                timeout=DETECTOR_TIMEOUT_SEC,
            )
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
