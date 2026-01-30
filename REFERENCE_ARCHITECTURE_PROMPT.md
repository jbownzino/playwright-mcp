# Reference Architecture – Image Prompt for Demo

Use the text below (or a shortened version) as the prompt for your image model (DALL·E, Midjourney, Ideogram, etc.) to generate a clean reference architecture diagram.

---

## Full prompt (copy-paste)

**Prompt:**

A clean, professional reference architecture diagram, infographic style, soft colors and simple shapes. Not photorealistic. Four horizontal layers with rounded rectangles and thin arrows between them. From top to bottom:

1. **Top layer:** One box labeled "Monitor Script (Python)" — represents the harmful content detection runner.
2. **Second layer:** Two boxes side by side — "Browser-Use Agent" (orchestrates actions) and "LLM / Vision API" (e.g. Gemini) with a two-way arrow between them.
3. **Third layer:** One box labeled "Browser (Browser-Use)" with an arrow down from the Agent and an arrow from the LLM (screenshots in, actions out).
4. **Bottom layer:** One box labeled "Game (Phaser 3 + Vite, localhost)" — the basketball game that shows modals.

Arrows show flow: Monitor → Agent; Agent ↔ LLM; Agent → Browser; Browser → Game. (This project uses Browser-Use for browser control only — no direct Playwright in the app.) Minimal text, no code. White or light gray background, blue/gray accents. Suitable for a demo slide.

---

## Short prompt (if character limit is tight)

**Prompt:**

Reference architecture diagram, infographic style, simple and clean. Four horizontal layers: (1) Monitor Script – Python, (2) Browser-Use Agent and LLM/Vision API with two-way link, (3) Browser – Browser-Use, (4) Game – Phaser 3 on localhost. Rounded boxes, thin arrows showing data/control flow. Soft blue-gray palette, white background. Professional slide-ready, not photorealistic.

---

## Optional: add to the prompt for “realistic but not too detailed”

- “Slightly isometric or flat 2D layout.”
- “Like a cloud or SaaS architecture diagram, but for a single app.”
- “Only 5–7 labeled boxes; no small print or code snippets.”
