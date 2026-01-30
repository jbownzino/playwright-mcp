# Reference Architecture – Image Prompt for Demo

Use the text below (or a shortened version) as the prompt for your image model (DALL·E, Midjourney, Ideogram, etc.) to generate a clean reference architecture diagram.

---

## Full prompt (copy-paste)

**Prompt:**

A clean, professional reference architecture diagram, infographic style, soft colors and simple shapes. Not photorealistic. Four horizontal layers with rounded rectangles and thin arrows between them. From top to bottom:

1. **Top layer:** One box labeled "Monitor Script (Python)" — orchestrates Player, Detector, and Judge; harmful content detection runner.
2. **Second layer:** Two boxes side by side — "Browser-Use (Player + Detector)" and "LLM / Vision API (e.g. Gemini)". Browser-Use: Player sends fast clicks to the game; Detector takes screenshots and triggers LLM classification. LLM: used for semantic detection (screenshot → harmful type) and for Judge (evaluate task completion). Two-way arrow between them (screenshots in, classifications + judge verdict out).
3. **Third layer:** One box labeled "Chrome (Browser-Use)" — receives clicks and screenshot requests from the script; drives the game page. Put the Chrome logo here as well.
4. **Bottom layer:** One box labeled "Game (Phaser 3 + Vite, localhost)" — basketball game that shows harmful-content modals.

Arrows: Monitor → Browser-Use and Monitor → LLM; Browser-Use ↔ LLM; Browser-Use → Browser; Browser → Game. This project uses Browser-Use for browser control only (no direct Playwright). Minimal text, no code. White or light gray background, blue/gray accents. Suitable for a demo slide.

---

## Short prompt (if character limit is tight)

**Prompt:**

Reference architecture diagram, infographic style, simple and clean. Four horizontal layers: (1) Monitor Script – Python (Player, Detector, Judge), (2) Browser-Use (Player + Detector) and LLM/Vision API (Detection + Judge) with two-way link, (3) Browser – Browser-Use, (4) Game – Phaser 3 on localhost. Rounded boxes, thin arrows showing data/control flow. Soft blue-gray palette, white background. Professional slide-ready, not photorealistic.

---

## Optional: add to the prompt for "realistic but not too detailed"

- "Slightly isometric or flat 2D layout."
- "Like a cloud or SaaS architecture diagram, but for a single app."
- "Only 5–7 labeled boxes; no small print or code snippets."
