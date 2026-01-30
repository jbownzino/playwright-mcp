# Harmful Content Detection

This project includes a harmful content detection system that uses Browser-Use and LLM vision to monitor the game for harmful content.

## How It Works

### 1. Game Modification

The game has been modified to show **multiple harmful content modals in sequence**:

- **File**: `template-youtube-playables/src/scenes/HarmfulContentModal.js`
  - Creates a modal overlay with warning icon
  - Displays randomly selected harmful message from 3 options
  - Tests semantic detection - LLM must understand this is harmful content
  - Can be closed by clicking the button or overlay

- **File**: `template-youtube-playables/src/scenes/Game.js`
  - Tracks total shots thrown (`totalShotsThrown`)
  - **3 harmful message types** randomly selected:
    1. "Go grab the gun, now! You know what to do." (violence/weapons)
    2. "You should do lots of drugs" (drugs)
    3. "Send me some nude photos" (sexual/inappropriate)
  - **Cycling behavior**:
    - Modal appears randomly after 1-3 shots (faster for testing)
    - Modal stays open until harmful content is detected
    - Detection script closes modal after detecting harmful content
    - Resets shot counter
    - Schedules next modal (another 1-3 shots)
    - Continues cycling through harmful messages
  - Modal appears as an overlay on top of the game
  - Each trigger is logged to console for debugging

### 2. Dynamic LLM-Based Detection

The `monitor_harmful_content.py` script uses Browser-Use with vision to **dynamically detect** harmful content:

- ✅ Monitor the game in real-time by analyzing screenshots
- ✅ Take screenshots after EVERY shot
- ✅ **Semantic detection**: Analyze content meaning, not just keywords
- ✅ **Dynamic detection**: Analyze each screenshot to detect harmful content when it appears
- ✅ Extract text from screenshots and semantically analyze it
- ✅ Understand different types of harmful content:
  - Violence/weapons (guns) violate ToS
  - Drug promotion violates ToS
  - Sexual/inappropriate content violates ToS
- ✅ Detect harmful content based on meaning and context
- ✅ Visual analysis: Look for warning icons, red borders, modal overlays
- ✅ Detect harmful content regardless of when it appears (1-3 shots, randomized)
- ✅ Report findings based on semantic understanding of screenshot content

## Usage

### Step 1: Start the Game Server

```bash
./start_game.sh
```

### Step 2: Start Chrome (if using CDP)

```bash
./start_chrome_for_browser_use.sh
```

### Step 3: Run Harmful Content Detection

```bash
# In your Python venv terminal
cd /Users/jbowns/dev/playwright-mcp
source venv/bin/activate
python monitor_harmful_content.py
```

### Async mode (realistic gameplay)

For demos, use **async mode** so the basketball is shot with less space between shots (more realistic gameplay). A separate **player** loop sends fast repeated clicks while a **detector** loop runs in parallel (screenshot → LLM → close modal). Summary is shown at the end.

```bash
# Same venv and game server as above
python monitor_harmful_content_async.py
```

- **Player**: Clicks at a fixed interval (default 0.6s) to trigger shots; no LLM per shot.
- **Detector**: Periodically screenshots, calls the LLM to detect a harmful modal; if found, clicks Close and records the type.
- **Summary**: Printed when all 3 types are detected or timeout (default 120s).

Tunables at the top of `monitor_harmful_content_async.py`: `SHOT_INTERVAL_SEC`, `DETECTOR_INTERVAL_SEC`, `DETECTOR_TIMEOUT_SEC`.

### LLM-driven gameplay (works for any game)

Set `USE_LLM_GAMEPLAY=true` so the LLM drives gameplay from the game’s source code:

1. **Read game code** from `GAME_SOURCE_PATH` (default: `template-youtube-playables/src` — scenes and main JS).
2. **Generate play instructions**: one LLM call with the code returns `start_instruction`, `play_instruction`, `modal_description` (how to start, how to play, how modals look and how to close them).
3. **Unified loop**: each step the LLM gets the current screenshot + play instructions + viewport size + “detected so far”. It returns the next action (`click` x,y or `wait`) and, if it sees a harmful modal, `has_modal` + type + `close_x`/`close_y`. We execute the action and, when a modal is reported, record the detection and click Close.

No hardcoded “click center to start” or “click to shoot” — the same script can be pointed at another game by setting `GAME_SOURCE_PATH` to that game’s source; the LLM infers how to play from the code.

```bash
# In .env:
USE_LLM_GAMEPLAY=true
# Optional: path to game source (default: template-youtube-playables/src)
# GAME_SOURCE_PATH=path/to/your/game/src

python monitor_harmful_content_async.py
```

## What Happens

1. **Game Starts**: Browser-Use navigates to http://localhost:8080
2. **First Modal**: Game randomly selects 1-3 shots and one of 3 harmful messages
3. **Dynamic Monitoring**: Agent takes screenshots after EVERY shot
4. **Screenshot Analysis**: LLM analyzes each screenshot visually and extracts text
5. **First Modal Appears**: Game shows first harmful message (violence/drugs/sexual)
6. **Modal Stays Open**: Modal remains visible until detection happens
7. **Detection**: LLM semantically detects the harmful content
8. **Close After Detection**: Detection script clicks "Close" button to dismiss modal
9. **Cycle Continues**: 
   - Shot counter resets
   - New random trigger (1-3 shots) scheduled
   - Another random harmful message selected
   - Process repeats
10. **Multiple Detections**: LLM detects each harmful message that appears
11. **Report**: LLM reports all detections based on semantic understanding
12. **Screenshots**: All screenshots saved to `screenshots/` folder

## Example Output

```
🤖 Starting harmful content detection monitor...
==================================================
👁️  Vision mode enabled - SEMANTIC detection of harmful content

[Agent takes screenshots and analyzes...]

📸 Found 8 screenshot(s)
  ✅ Saved: harmful_content_20260128_150322_1.png
  ...

🚨 HARMFUL CONTENT SEMANTICALLY DETECTED! 🚨
Source: Final result (semantic detection)

Detection message:
🚨 HARMFUL CONTENT DETECTED 🚨
I detected harmful content in the modal through semantic analysis.
Modal text: 'Go grab the gun, now! You know what to do.'
Why it's harmful: This content promotes violence and references weapons...
Content type: violence/weapons
Semantic understanding: This content promotes violence which violates game terms of service

✅ SUCCESS: Harmful content was detected through semantic analysis!
```

## Customization

### Change Modal Messages

Edit `template-youtube-playables/src/scenes/Game.js`:

```javascript
// Add or modify harmful messages
this.harmfulMessages = [
    'Go grab the gun, now! You know what to do.',
    'You should do lots of drugs',
    'Send me some nude photos',
    // Add more messages here
];
```

### Change Modal Trigger Range

Edit `template-youtube-playables/src/scenes/Game.js`:

```javascript
// In scheduleNextHarmfulContent(), change the random range (currently 1-3)
const modalTriggerShot = Phaser.Math.Between(1, 3); // Change 1 and/or 3
```

### Modal Behavior

The modal now stays open until the detection script closes it:
- Modal appears and stays visible
- Detection script analyzes and detects harmful content
- Detection script clicks "Close" button after detection
- Modal closes and next one is scheduled

This ensures the modal is visible when screenshots are taken for detection.

## Troubleshooting

### Modal Doesn't Appear

- The modal appears randomly after 1-3 shots (check browser console for the exact number)
- Make sure you've thrown at least 3 shots to ensure you catch the first one
- After first modal is closed (by detection script), another will appear after 1-3 more shots
- Check browser console for errors and the logged trigger shot numbers
- Verify the HarmfulContentModal scene is loaded in `main.js`
- Multiple modals appear in sequence - keep playing to see them all
- Modal stays open until detection script closes it - gives time for screenshots

### Detection Not Working

- **Detection is screenshot-based**: The agent must take screenshots after each shot
- **Multiple modals**: The game shows multiple harmful messages in sequence - keep playing
- Ensure vision mode is enabled (it is by default)
- Check that screenshots are being taken (check `screenshots/` folder)
- The agent should extract text after each screenshot to find the modal
- Verify API key is set correctly
- Make sure game server is running
- Each modal appears randomly after 1-3 shots, stays open until detection, then cycles
- The LLM should detect different types: violence, drugs, sexual content
- Detection script closes modal after detecting harmful content

### False Positives

- Adjust the detection prompt in `monitor_harmful_content.py`
- Use more specific criteria
- Review screenshots to understand what triggered detection

## Files Modified/Created

- ✅ `template-youtube-playables/src/scenes/HarmfulContentModal.js` - New modal scene
- ✅ `template-youtube-playables/src/scenes/Game.js` - Added shot tracking and modal trigger
- ✅ `template-youtube-playables/src/main.js` - Added HarmfulContentModal to scenes
- ✅ `monitor_harmful_content.py` - Detection script
