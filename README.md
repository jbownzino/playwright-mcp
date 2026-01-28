# Playwright MCP - Browser-Use Project (Open Source)

Python 3.12 project with Browser-Use for AI-powered browser automation.

**Browser-Use is open-source** - this setup uses the open-source version with local browser automation and your choice of LLM provider.

## Quick Setup

### 1. Virtual environment is already created

Activate it:
```bash
source venv/bin/activate
```

### 2. Install Browser-Use

Run the installation script:
```bash
./install_browser_use.sh
```

Or manually:
```bash
# Using uv (recommended)
uv pip install browser-use

# Or using pip
pip install browser-use

# Install Chromium browser
uvx browser-use install
```

### 3. Configure LLM API Key

Browser-Use is open-source and works with any supported LLM provider. Choose one:

**Option 1: Google Gemini (Recommended - Free tier available)**
1. Copy the example env file: `cp .env.example .env`
2. Get your free API key at: https://aistudio.google.com/app/u/1/apikey?pli=1
3. Add it to `.env` file:
```bash
GOOGLE_API_KEY=your_api_key_here
```

**Option 2: OpenAI**
1. Get your API key from https://platform.openai.com/api-keys
2. Add to `.env`:
```bash
OPENAI_API_KEY=your_api_key_here
```
3. Update `quickstart.py` to use `ChatOpenAI` instead of `ChatGoogle`

**Option 3: Anthropic Claude**
1. Get your API key from https://console.anthropic.com/
2. Add to `.env`:
```bash
ANTHROPIC_API_KEY=your_api_key_here
```
3. Update `quickstart.py` to use `ChatAnthropic` instead of `ChatGoogle`

### 4. Run Quickstart

**Default task:**
```bash
python quickstart.py
```

**Custom task (pass as argument):**
```bash
python quickstart.py "Search for Python tutorials on YouTube"
python quickstart.py "Find the weather in San Francisco"
```

**Or use the flexible task runner:**
```bash
python run_task.py "Your custom task here"
```

## Project Structure

- `quickstart.py` - Example Browser-Use agent (accepts tasks as command-line arguments)
- `run_task.py` - Flexible task runner for custom Browser-Use tasks
- `play_game.py` - **Game automation script** - interact with local game at http://localhost:8080
- `vision_example.py` - Example demonstrating vision capabilities (screenshot understanding)
- `start_game.sh` - Start the Vite game server
- `examples.md` - Examples of different tasks you can run
- `VISION.md` - Guide to Browser-Use vision capabilities
- `GAME_AUTOMATION.md` - **Guide for automating the local game**
- `template-youtube-playables/` - Phaser 3 game (Basketball Shoot Out)
- `screenshots/` - Screenshots from Browser-Use automation (automatically saved here)
- `.env.example` - Template for environment variables (copy to `.env` and add your API key)
- `.env` - Your environment variables (gitignored - add your API key here)
- `requirements.txt` - Python dependencies
- `install_browser_use.sh` - Installation script for Browser-Use and Chromium
- `start_chrome_for_browser_use.sh` - Helper to start Chrome with remote debugging

## Usage

After activating the virtual environment:

**Run tasks:**
- Default task: `python quickstart.py`
- Custom task: `python quickstart.py "Your task here"`
- Flexible runner: `python run_task.py "Your task here"`

**Examples:**
```bash
python run_task.py "Search for Python tutorials"
python run_task.py "Find the top story on Hacker News"
python run_task.py "Go to github.com and search for 'browser automation'"
```

**Screenshots & Vision:**
- Screenshots are automatically saved to the `screenshots/` folder
- Each screenshot is timestamped and named based on the task
- Screenshots are gitignored (won't be committed to git)
- **Vision is enabled by default** - Browser-Use can "see" screenshots to understand page layout and get coordinates
- See `VISION.md` for details on vision capabilities

**Game Automation:**
- **Automate the local Phaser game** running on http://localhost:8080
- Start game server: `./start_game.sh`
- Run automation: `python play_game.py "your task"`
- Vision mode is essential for games (Canvas-based) - automatically enabled
- See `GAME_AUTOMATION.md` for detailed game automation guide

**Harmful Content Detection:**
- **Monitor game for harmful content** using LLM vision
- After 4 shots, a modal appears saying "This is harmful content"
- Run monitor: `python monitor_harmful_content.py`
- The LLM analyzes screenshots to detect harmful content in real-time

See `examples.md` for more task examples and tips.

**Other commands:**
- Install packages: `pip install <package-name>` or `uv pip install <package-name>`
- Create new agents: See `quickstart.py` or `run_task.py` for examples

## Browser-Use Documentation

- [Quickstart Guide](https://docs.browser-use.com/getting-started/quickstart)
- [Agent Documentation](https://docs.browser-use.com/customize/agent/basics)
- [Browser Configuration](https://docs.browser-use.com/customize/browser/basics)
- [Tools & Actions](https://docs.browser-use.com/customize/tools/available)

## Deactivate virtual environment

```bash
deactivate
```
