# Browser-Use Vision Capabilities

## Yes! Browser-Use Can Understand Screenshots and Get Coordinates

Browser-Use has built-in **vision capabilities** that allow it to:
- ✅ See and understand screenshots
- ✅ Identify elements on the page visually
- ✅ Get coordinates for clicking/interacting
- ✅ Understand page layout and structure
- ✅ Work with complex UIs that are hard to automate with DOM alone

## How It Works

1. **Screenshot Capture**: Browser-Use automatically takes screenshots during automation
2. **Vision Analysis**: The LLM (like Gemini) analyzes the screenshot to understand:
   - What elements are visible
   - Where they are located (coordinates)
   - What they look like (colors, text, buttons, etc.)
   - How to interact with them
3. **Action Execution**: Uses the visual understanding to click, type, scroll, etc.

## Vision Modes

### `use_vision="auto"` (Recommended - Default)
- Smart mode: Uses vision when needed
- Includes screenshot tool but only uses vision when requested
- Most efficient - balances accuracy and speed

### `use_vision=True`
- Always includes screenshots in every step
- Maximum accuracy for complex UIs
- Slower and more expensive (more API calls)

### `use_vision=False`
- Never uses vision
- Relies only on DOM/HTML structure
- Fastest but may struggle with complex UIs

## Vision Detail Levels

### `vision_detail_level="auto"` (Default)
- Automatically chooses detail level based on task

### `vision_detail_level="low"`
- Faster, lower cost
- Good for simple pages

### `vision_detail_level="high"`
- More detailed analysis
- Better for complex UIs, visual elements
- Higher cost but better accuracy

## Example: Using Vision

```python
from browser_use import Agent, Browser, ChatGoogle

agent = Agent(
    task="Click the blue button in the top right corner",
    llm=ChatGoogle(model="gemini-flash-latest"),
    browser=browser,
    use_vision="auto",  # Enable vision
    vision_detail_level="high",  # High detail for better accuracy
)

history = await agent.run()
```

## What Vision Can Do

### Visual Element Detection
```python
# Task: "Click the red 'Submit' button"
# Agent sees screenshot → identifies red button → gets coordinates → clicks
```

### Layout Understanding
```python
# Task: "Find the navigation menu and click 'About'"
# Agent analyzes screenshot → understands page layout → finds menu → clicks
```

### Color/Visual Recognition
```python
# Task: "Click the green button on the left side"
# Agent sees screenshot → identifies green button → gets position → clicks
```

### Complex UI Interaction
```python
# Task: "Fill out the form with the blue background"
# Agent sees screenshot → identifies form visually → fills it out
```

## When Vision is Most Useful

✅ **Use vision when:**
- Elements are hard to find with DOM selectors
- Working with visual-heavy UIs (dashboards, games, etc.)
- Need to identify elements by appearance (color, position)
- Dealing with dynamic content that changes frequently
- Complex layouts with overlapping elements

❌ **Vision may not be needed when:**
- Simple forms with clear IDs/classes
- Well-structured HTML pages
- Speed is critical (vision adds latency)
- Cost is a concern (vision uses more tokens)

## Example Tasks That Benefit from Vision

```python
# Visual element identification
"Click the blue button in the top right"

# Layout-based navigation
"Find the sidebar menu and click 'Settings'"

# Color-based selection
"Click the green 'Success' message"

# Visual form filling
"Fill out the form with the red border"

# Complex UI interaction
"Navigate to the dashboard and find the chart"
```

## Accessing Screenshots

After running a task, you can access screenshots:

```python
history = await agent.run()

# Get all screenshot paths
screenshots = history.screenshot_paths()

# Get screenshots as base64 strings
screenshots_base64 = history.screenshots()

# View screenshot paths
for path in screenshots:
    print(f"Screenshot: {path}")
```

## Tips for Best Results

1. **Be descriptive**: "Click the blue button" works better than "click button"
2. **Use visual cues**: Mention colors, positions, sizes
3. **Combine with actions**: "Use screenshot to see the page, then click the login button"
4. **High detail for complex UIs**: Use `vision_detail_level="high"` for dashboards, games, etc.

## Try It Out

Run the vision example:
```bash
python vision_example.py "Go to example.com and describe what you see"
```

Or use vision in your tasks:
```bash
python run_task.py "Click the blue button in the top right corner"
```

The agent will automatically use vision to understand the screenshot and find the coordinates!
