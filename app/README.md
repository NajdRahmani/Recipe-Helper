# Savour — a redesigned Recipe Helper Web UI

A responsive, dependency-free frontend for the existing **single n8n Recipe Helper supervisor** workflow. It does **not** change the AI, Chef, Validator, Qdrant, or Ollama workflow.

## Files

- `index.html` — accessible page structure
- `styles.css` — responsive visual design
- `app.js` — webhook client, JSON parsing, photo support, pantry, saved recipes, cooking steps

## Run locally

From this folder:

```bash
python -m http.server 8000
```

Visit **http://localhost:8000**.

Open the **gear icon → Webhook settings** and set your n8n URL, e.g.:

- Active n8n workflow: `http://localhost:5678/webhook/recipe-helper`
- Listen for test event: `http://localhost:5678/webhook-test/recipe-helper`
- Best if served behind the same reverse proxy: `/webhook/recipe-helper`

You can open the page without connecting a webhook and press **See example result** to view a clearly labeled demo.

## Webhook request contract

The frontend POSTs JSON to the configured endpoint:

```json
{
  "query": "I have eggs and tomatoes",
  "filters": {
    "max_minutes": 30,
    "vegetarian": true,
    "max_kcal": 400,
    "min_protein_g": 12,
    "cuisine": "italian"
  }
}
```

When an image is attached, it adds `"image_b64":"<raw base64 without data URL prefix>"`.

All filters are optional; absent fields are omitted from `filters`.

## Expected webhook response

The existing **Build Final or Return Issues** node in the n8n validation sub-tool produces a `final_json` recipe. **Format Webhook Response** in the main workflow sends that object directly:

```json
{
  "name": "orange juice spritzer",
  "minutes": 10,
  "kcal": 61,
  "protein_g": 0.5,
  "carbs_g": null,
  "fat_g": null,
  "ingredients": ["frozen orange juice concentrate", "water", "lemon juice", "carbonated lemon-lime beverage"],
  "steps": ["Combine ingredients", "Stir gently"],
  "chef_note": "Stir gently to preserve the fizz.",
  "substitutions": [],
  "have": [],
  "missing": [],
  "image_url": null,
  "agentic_review": {"status":"approved", "validator":"passed"}
}
```

The frontend also accepts an object wrapped in `final_json`, `json`, `result`, `data`, or `output`, and handles an `{ "error": "..." }` response.

## User-facing features

- Beautiful editorial, responsive design with original SVG citrus artwork
- Text and image inputs; file compression before upload; drag-and-drop photo
- Filter controls matching your existing n8n payload keys
- Structured, safely escaped recipe rendering — **no raw Markdown/HTML rendering**, which prevents erroneous `canvascanvas` markup
- Clear **AI reviewed** badge only when `agentic_review.status === "approved"`
- Ingredient checklists, progress counters, step completion, focused step-by-step cooking drawer
- Copy recipe, copy ingredients, print
- Saved recipes and personal pantry held in the user's browser via localStorage
- Human-readable errors for unreachable webhook, timeout, invalid responses
- Demo recipe clearly marked **preview** (not a real live validation)

## CORS and production hosting

If this UI is hosted on `localhost:8000` while n8n runs on `localhost:5678`, the origins are **different**. The browser may reject requests unless n8n (or a reverse proxy) sends the appropriate `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods: POST, OPTIONS`, and `Access-Control-Allow-Headers: Content-Type` responses, including to the preflight request.

**Recommended deployment:** Serve the frontend and proxy `/webhook/recipe-helper` to n8n under the **same origin** (e.g. using Nginx). Configure the endpoint as `/webhook/recipe-helper`. Secure your production webhook at the reverse proxy or via a server-side auth layer; do not place long-lived secrets in browser JavaScript.

Never use an unrestricted `*` origin with credentialed requests. This frontend uses no cookies or authentication headers by default.

## Tests performed

- JavaScript syntax check with Node.js
- Desktop (1440px), tablet (820px), and mobile (390px) Chromium rendering (no horizontal overflow)
- Client-side test of saved recipes, ingredient checkboxes, cooking drawer, and webhook settings
- A **mocked webhook** returning the actual expected JSON shape, including approved validation metadata

**Not tested:** a live cross-origin fetch to your n8n 2.42.4 instance. Validate CORS and the production webhook independently.

## All-food redesign
Hero showcases pasta, salad, stew and dessert. Demo shows shakshuka. Search, uploads, filters and n8n integration are recipe-agnostic.
