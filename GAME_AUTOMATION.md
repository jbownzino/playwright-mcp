# Game Automation with Browser-Use

This project includes a Phaser 3 game (Basketball Shoot Out) that runs locally and can be automated with Browser-Use.

## Quick Start

### 1. Start the Game Server

In one terminal:
```bash
./start_game.sh
```

Or manually:
```bash
cd template-youtube-playables
npm install  # First time only
npm run dev
```

The game will be available at: **http://localhost:8080**

### 2. Start Chrome with Remote Debugging

In another terminal (if using CDP mode):
```bash
./start_chrome_for_browser_use.sh
```

Make sure `USE_CDP=true` is set in your `.env` file.

### 3. Run Browser-Use Automation

```bash
# Default: Play the game and interact with it
python play_game.py

# Custom task
python play_game.py "Click the start button and shoot the basketball 5 times"

# More specific tasks
python play_game.py "Navigate to the game, click start, and play until game over"
python play_game.py "Take a screenshot of the main menu"
```

## How It Works

### Vision Mode for Games

Games (especially Canvas-based games like Phaser) are **visual** - they don't have traditional DOM elements. Browser-Use uses **vision mode** to:

- ✅ See the game canvas
- ✅ Identify game elements visually (buttons, sprites, UI)
- ✅ Get coordinates for clicking/interacting
- ✅ Understand game state from screenshots

The `play_game.py` script automatically:
- Enables `use_vision=True` (always on for games)
- Uses `vision_detail_level="high"` for better accuracy
- Checks if the game server is running before starting

### Example Tasks

**Basic Interaction:**
```bash
python play_game.py "Click the start button"
```

**Gameplay:**
```bash
python play_game.py "Start the game and shoot the basketball 3 times"
python play_game.py "Play the game and try to score points"
```

**Screenshots:**
```bash
python play_game.py "Take a screenshot of the game menu"
```

**Complex Tasks:**
```bash
python play_game.py "Navigate to the game, click start, play one round, and tell me the final score"
```

## Game Details

- **Type**: Phaser 3 YouTube Playables Template
- **Game**: Basketball Shoot Out
- **URL**: http://localhost:8080
- **Port**: 8080 (configured in `vite/config.dev.mjs`)

## Troubleshooting

### Game Server Not Running

If you see "Game server not found":
1. Make sure `./start_game.sh` is running
2. Check that port 8080 is not in use: `lsof -i :8080`
3. Verify the game loads in your browser: http://localhost:8080

### Browser-Use Can't See Game Elements

- Vision mode is **required** for games (already enabled in `play_game.py`)
- Make sure Chrome is running with `headless=False` so you can see what's happening
- Try being more specific: "Click the blue start button" vs "click start"

### Chrome Not Connecting

- Make sure Chrome is started with remote debugging: `./start_chrome_for_browser_use.sh`
- Check `USE_CDP=true` in `.env`
- Verify Chrome debugging: `curl http://127.0.0.1:9222/json/version`

## Tips for Game Automation

1. **Be Visual**: Describe what you see - "Click the blue button" works better than "click button"
2. **Use Screenshots**: The agent takes screenshots automatically - check the `screenshots/` folder
3. **Watch the Browser**: Keep `headless=False` to see what the agent is doing
4. **Game State**: Games are stateful - "play until game over" works better than individual actions

## Project Structure

```
playwright-mcp/
├── template-youtube-playables/    # The Phaser game
│   ├── src/                       # Game source code
│   ├── public/                    # Game assets
│   └── vite/                      # Vite configuration
├── play_game.py                   # Browser-Use automation script
├── start_game.sh                  # Start the game server
└── screenshots/                   # Screenshots from automation
```

## Next Steps

- Customize `play_game.py` for your specific automation needs
- Add custom tasks for testing game features
- Use screenshots to debug automation issues
- Integrate with game testing workflows
