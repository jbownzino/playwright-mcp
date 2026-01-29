# Browser-Use Task Examples

## Ways to Give Commands to Browser-Use

### Method 1: Command-Line Arguments (Recommended)

```bash
# Run a custom task
python quickstart.py "Search for Python tutorials on YouTube"

# Or use the flexible runner
python run_task.py "Find the latest news about AI"

# Multi-word tasks (use quotes)
python run_task.py "Go to github.com and find the most popular Python repository"
```

### Method 2: Environment Variable

```bash
export BROWSER_USE_TASK="Search for weather in San Francisco"
python run_task.py
```

### Method 3: Edit the Script Directly

Edit `quickstart.py` and change the `task` variable:

```python
task = "Your custom task here"
```

## Example Tasks

### Web Search & Information Gathering
```bash
python run_task.py "Search for the best Python web frameworks in 2024"
python run_task.py "Find the top 5 programming languages on GitHub"
python run_task.py "What's the weather forecast for New York?"
```

### Website Navigation
```bash
python run_task.py "Go to news.ycombinator.com and find the top story"
python run_task.py "Navigate to github.com and search for 'browser automation'"
python run_task.py "Visit duckduckgo.com and search for 'Python async programming'"
```

### Data Extraction
```bash
python run_task.py "Go to quotes.toscrape.com and extract the first 5 quotes"
python run_task.py "Find the price of Bitcoin on coinbase.com"
python run_task.py "Extract the headlines from bbc.com/news"
```

### Form Filling & Interaction
```bash
python run_task.py "Go to example.com/contact and fill out the contact form with test data"
python run_task.py "Search for 'Python' on google.com and click the first result"
```

### Complex Multi-Step Tasks
```bash
python run_task.py "Go to github.com, search for 'playwright', open the first result, and find the number of stars"
python run_task.py "Search for 'Python tutorials' on YouTube, open the first video, and tell me the title"
python run_task.py "Find the CEO of OpenAI by searching on their website"
```

## Advanced: Using Specific Actions

You can be more specific about what actions to use:

```bash
# Use specific actions
python run_task.py "Use the search action to find 'Python', then use click to open the first result, then use extract to get the page title"

# Navigate and extract
python run_task.py "Navigate to https://example.com, wait 2 seconds, then extract all headings"
```

## Tips for Better Results

1. **Be Specific**: Instead of "search", say "use the search action to find..."
2. **Break Down Complex Tasks**: "Go to X, then do Y, then do Z"
3. **Name Actions Directly**: "Use click action", "Use extract action"
4. **Include URLs**: "Go to https://example.com" is clearer than "visit example"

## Running Multiple Tasks

Create a script to run multiple tasks:

```python
# batch_tasks.py
import asyncio
from run_task import run_task

tasks = [
    "Find the top story on Hacker News",
    "Search for Python tutorials",
    "Get the weather in San Francisco"
]

async def main():
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"Running: {task}")
        print('='*60)
        await run_task(task)

if __name__ == "__main__":
    asyncio.run(main())
```
