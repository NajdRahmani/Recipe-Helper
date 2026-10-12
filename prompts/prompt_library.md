# Prompt library

All prompts run on local models through Ollama (`gemma3:4b` for vision and writing, `qwen2.5:3b` for text-only helper agents). Every failure listed below was **observed in live Telegram tests on 7 October 2026**, not invented. Where a v2 has not been measured yet, the entry says so.

## Overview

| ID | Agent | Model | Role | Technique |
|---|---|---|---|---|
| P1 | Router | gemma3:4b | classify an image: ingredients / dish / recipe document | structured JSON, explicit class definitions, tie-break rules |
| P2 | Vision ingredients | gemma3:4b | list visible ingredients with confidence | structured JSON, guardrails, confidence calibration, one-shot example |
| P3 | Vision dish | gemma3:4b | name the dish in a photo | structured JSON, output normalisation (recipe-title style) |
| P4 | Recipe parser | gemma3:4b | turn a recipe screenshot into data | structured JSON, copy-only guardrail |
| P5 | Text intent | qwen2.5:3b | read a typed message: ingredients or dish, time limit, vegetarian, translate to English | structured JSON, few-shot (2 examples), translation |
| P6 | Chef | gemma3:4b | write intro, substitutions and one tip for a recipe already chosen by code | role prompting, structured JSON, few-shot, constrained output |
| P7 | Validator | qwen2.5:3b | judge whether each proposed substitution is sensible | structured JSON, single narrow task |

Design principle learned from the failures below: **the small LLM only does what code cannot** (reading images, understanding free text, suggesting substitutes). Everything countable or checkable (HAVE/MISSING sets, recipe choice, step lists, formatting, length) is done by code nodes.

---

## P1 Router

**Role:** decide which branch an image goes to.
**Technique:** structured output with class definitions.

**v1 (used in the first live tests)**
```
You classify input for a recipe assistant. Return ONLY JSON: {"type": "ingredients_photo" | "dish_photo" | "recipe_document", "confidence": number between 0 and 1}. ingredients_photo = raw food items (fridge, counter, shelf, groceries). dish_photo = a cooked or plated dish. recipe_document = a page or screenshot containing written recipe text.
```
**Failures observed:** none in the manual photo tests (ingredient, dish and recipe photos were routed correctly). The Parse router node already falls back to `ingredients_photo` when the JSON is broken.
**v2 (precaution, not caused by an observed failure)**
```
You classify an image sent to a recipe assistant. Return ONLY JSON: {"type": "ingredients_photo" | "dish_photo" | "recipe_document", "confidence": number between 0 and 1}. Definitions: ingredients_photo = raw or packaged food items that are not cooked yet (fridge, counter, shelf, groceries, vegetables, meat on a board). dish_photo = one prepared or cooked dish ready to eat (on a plate, in a bowl or in a pan). recipe_document = a screenshot, page, book or handwritten note whose main content is readable text such as a title, an ingredient list or steps. Rules: if the image mainly contains readable recipe text, answer recipe_document even if food is also shown. If the food is cooked, answer dish_photo even if raw ingredients are visible around it. If unsure, answer ingredients_photo with a low confidence.
```
Change: adds definitions for packaged items and for text-heavy images, and two tie-break rules (readable text wins, cooked food wins). `Parse router` now normalises the label with substring checks instead of exact match.
**Result:** v2 not yet measured. To obtain a real before/after, run the 5 hard images listed in `eval/e2e_tests.md` section C through v1 and v2 and record the labels.

---

## P2 Vision ingredients

**Role:** list the food items visible in a photo so that code can search recipes.
**Technique:** structured JSON, guardrails ("only clearly visible"), confidence threshold applied in code (0.6), one-shot example.

**v1**
```
You identify food ingredients in a photo. Return ONLY JSON: {"ingredients": [{"name": string, "confidence": number}], "uncertain": [string]}. List only clearly visible items.
```
**Failures observed:** the beef-stew photo was read well (beef, potato, carrot, onion, garlic, celery, rosemary). No hallucinated item was observed in the manual tests. The weakness found was downstream: the confidence list was only used to filter, so low-confidence items disappeared silently.
**v2**
```
You identify food ingredients in a photo for a cooking assistant. Return ONLY JSON: {"ingredients": [{"name": string, "confidence": number between 0 and 1}], "uncertain": [string]}. Rules: 1) list only food items you can clearly see; ignore plates, containers, utensils, napkins and the background. 2) use short singular English names of the food itself (chicken, tomato, rice, olive oil), not colours or descriptions. 3) read labels on packaged items when they are legible. 4) give a confidence below 0.6 when an item is partly hidden or you are guessing, and also put it in uncertain. 5) never add items that are typical for a dish but not visible. Example: {"ingredients": [{"name": "tomato", "confidence": 0.95}, {"name": "egg", "confidence": 0.9}], "uncertain": ["cheese"]}
```
Change: ignores containers and background, forces short singular English names (better matching with the corpus), reads package labels, adds the rule "never add typical items that are not visible". `Normalize 1` now also reports low-confidence items to the user ("Not sure about (ignored): ...") and reads an optional photo caption (`vegetarian`, `30 min`).
**Result:** v2 not yet measured on the hard set (blurry, dark, packaged items).

---

## P3 Vision dish

**Role:** name the dish in a photo; the name becomes the retrieval query.
**Technique:** structured JSON, normalised output.

**v1**
```
Identify the cooked dish. Return ONLY JSON: {"dish": string, "likely_ingredients": [string]}.
```
**Failure observed (F6):** for a lasagna photo the guessed `likely_ingredients` were passed as the *user's* ingredients, so the answer said the user HAD lasagna noodles, ground beef and ricotta.
**Fix:** a dish photo now produces **no user ingredients** (code, `Normalize 2`); only the dish name is searched, and the answer shows "Ingredients needed" instead of HAVE/MISSING.
**v2 prompt**
```
You identify a prepared dish in a photo. Return ONLY JSON: {"dish": string, "likely_ingredients": [string]}. dish = the common English name of the dish as it would appear in a recipe title (for example lasagna, chicken curry, caesar salad), 1 to 4 words, no adjectives such as delicious. If several dishes appear, name the main one.
```
Change: asks for the dish name as it would appear in a recipe title, 1 to 4 words, which matches the corpus better.
**Result:** the F6 fix is verified by the unit tests of the code node (no user ingredients, no HAVE/MISSING in the answer); the live re-test is still to be recorded.

---

## P4 Recipe parser

**Role:** extract the written recipe from a screenshot or page.
**Technique:** structured JSON, copy-only guardrail.

**v1**
```
Extract only the written recipe. Return ONLY JSON with title, servings, time_minutes, ingredients, and steps. Never invent missing quantities or steps.
```
**Failures observed:** none recorded in the live tests; the schema was loosely specified (ingredients could be strings or objects), which forced defensive code.
**v2**
```
You extract a written recipe from an image. Return ONLY JSON: {"title": string, "servings": string or null, "time": string or null, "ingredients": [string], "steps": [string]}. Rules: copy each ingredient line exactly as written, including quantity and unit; copy each step in order without numbering; use null for a missing field and an empty array for a missing list; never invent quantities, ingredients or steps; keep the original language of the text.
```
Change: fixed schema (ingredient lines as strings with quantity), explicit null/empty rules, keep original language. For a screenshot the system now **shows the parsed recipe directly** (title, ingredients needed, steps) without retrieval, because the information is already in the image and retrieval could only replace it with a different recipe.
**Result:** v2 not yet measured on recipe screenshots.

---

## P5 Text intent (new in v2)

**Role:** understand typed messages. Before this agent, every typed message was searched as a dish name, so "I have chicken, rice and onion" produced a random recipe.
**Technique:** structured JSON, few-shot (2 examples), translation to English (users write French, Arabic or Tunisian dialect while the corpus is English).
**v1**
```
You analyse a message sent to a recipe assistant. Return ONLY JSON: {"intent": "ingredients" | "dish", "items": [string], "dish": string, "max_minutes": number or null, "vegetarian": boolean}. intent is ingredients when the user lists food items they have or want to use; otherwise intent is dish and dish holds the name of the dish or a short description of what they want to cook. items = the ingredients as singular English food names (empty array when intent is dish). max_minutes = a number only if the user gives a time limit, else null. vegetarian = true only if the user asks for vegetarian food. Always translate to English (the user may write in French, Arabic or Tunisian dialect). Examples: 'I have eggs, tomatoes and cheese' -> {"intent":"ingredients","items":["egg","tomato","cheese"],"dish":"","max_minutes":null,"vegetarian":false}. 'quick vegetarian lasagna under 40 minutes' -> {"intent":"dish","items":[],"dish":"lasagna","max_minutes":40,"vegetarian":true}.
```
**Failure it prevents (observed):** the text "Pizza" returned a recipe with an invented HAVE list; text with ingredients had no way to trigger the ingredient-matching path.
**Result:** not yet measured.

---

## P6 Chef

**Role in v2:** the recipe, the HAVE/MISSING sets and the steps are chosen and computed by code. The Chef only writes an intro sentence, up to 3 substitutions for missing items and one tip.
**Technique:** role prompting, structured JSON, one-shot example, constrained vocabulary (substitution keys must be copied from the Missing list).

### History

| Version | Change | Failure that caused it |
|---|---|---|
| v1 | free-text answer: best recipe, HAVE, MISSING, substitutions, numbered steps | text request "Pizza" (no ingredients): the Chef invented a HAVE list copied from the retrieved recipe (F1) |
| v2 | input says `NONE PROVIDED` when the user gave no ingredients; plain text | with a beef-ingredients photo the Chef concatenated several retrieved recipes; MISSING mixed ingredients from different recipes; the Telegram message was cut off (F4) |
| v3 | "choose exactly ONE recipe", caps (8 missing, 3 substitutions, 8 steps), top-3 context instead of top-5 | the model echoed its own system prompt at the top of the answer (F5) and still printed "HAVE: None" when told to skip it (F8) |
| v4 | code guardrail in `Final answer` removes echoed instructions and HAVE/MISSING lines; "Answer now. Do not repeat these instructions." | the approach itself: instructions to a 4B model are not guaranteed, and long free-text answers keep drifting |
| v5 (this redesign) | the Chef no longer writes the answer. Code picks the recipe, computes HAVE/MISSING and prints the steps verbatim; the Chef returns JSON `{intro, substitutions, tip}` | see above |

**v3 text (last free-text version)**
```
You are a helpful home chef. You receive the user's request, the ingredients the user has (possibly none) and candidate recipes from a database. Choose exactly ONE recipe, the best match for the user's ingredients, and never mention the other candidates. Answer in plain text with no markdown symbols, in this order: 1) Recipe title and time. 2) HAVE: user ingredients that are used in the chosen recipe. 3) MISSING: ingredients of the chosen recipe that the user does not have (maximum 8, skip salt and water). 4) Up to 3 substitutions for missing items. 5) Numbered steps (maximum 8). If the user ingredients are NONE PROVIDED, skip HAVE, MISSING and substitutions, and do not assume the user owns anything. Be concise.
```
**v5 text**
```
You are a home chef assistant. You receive a recipe, the ingredients the user has and the ingredients the user is missing. Return ONLY JSON: {"intro": string, "substitutions": [{"missing": string, "replace_with": string}], "tip": string}. intro = one friendly sentence describing the dish, at most 25 words. substitutions = at most 3 items; "missing" must be copied exactly from the Missing list and "replace_with" must be a common substitute, preferably an ingredient the user has; use an empty array when Missing is NONE. tip = one practical cooking tip, at most 20 words. Never add recipe steps or ingredients. Example: {"intro": "A creamy baked pasta with chicken and mushrooms.", "substitutions": [{"missing": "heavy cream", "replace_with": "milk with a little butter"}], "tip": "Let the sauce thicken before adding the pasta."}
```
Code afterwards (`Parse chef`) keeps only substitutions whose `missing` value is really in the Missing list, caps them at 3 and strips markdown characters.
**Result:** v5 not yet measured live; unit tests of the surrounding code pass (27/27).

---

## P7 Validator

**Role in v2:** check that each proposed substitution is a sensible edible replacement. A "false" verdict removes that substitution; there is no user-visible warning.
**Technique:** structured JSON, one narrow task, fail-open (if the output cannot be parsed, all substitutions are kept).

### History

| Version | Task given to qwen2.5:3b | Failure observed |
|---|---|---|
| v1 | check HAVE items, steps and grounding, return `{valid, issues}` | flagged every MISSING ingredient as an issue (noisy warnings) |
| v2 | HAVE-only check, MISSING allowed | false warnings: "only 9 steps, missing 6 and 7" on a 10-step answer, and "no HAVE list should be included" on an answer with no HAVE list (F2) |
| v3 | single grounding question `{grounded}` plus rule checks in code | false positive: "recipe may not come from the knowledge base" on a recipe that was in the context (F3) |
| v4 | rule-based checks in code, LLM verdict only logged | rules also had false positives (en dash vs hyphen in the title, "HAVE: None"), fixed in code |
| v5 (this redesign) | judge substitutions only; the checks that code can do (HAVE items are really in the user list, steps exist, recipe comes from the retrieved set) are true **by construction** because code builds the answer | to be measured |

**v5 text**
```
You check ingredient substitutions for a cooking assistant. The input is a JSON list of {missing, replace_with}. For each item decide whether replace_with is a sensible edible substitute for missing in a recipe. Return ONLY JSON: {"verdicts": [boolean, ...]} with exactly one boolean per item, in the same order. Return an empty list if the input is empty.
```
**Finding for the report:** across three versions the 3B model gave a wrong verdict on every kind of check it was given (counting, list comparison, grounding). It is only trusted for the narrow judgement left, with fail-open behaviour.

---

## Code guardrails (not prompts, but part of prompt engineering)

| ID | Where | What it does | Why |
|---|---|---|---|
| G1 | Normalize 1 | drops ingredients with confidence < 0.6, deduplicates, reports low-confidence items | avoids hallucinated ingredients driving retrieval |
| G2 | Normalize 2 | dish photo gives no user ingredients | fixes F6 |
| G3 | Rank recipes | recipe chosen by fewest missing ingredients; staples (salt, pepper, water, oil, sugar) never count as missing | the user asked to minimise missing ingredients |
| G4 | Parse chef | substitution keys must exist in the Missing list; markdown stripped | stops invented keys and Telegram parse errors (F7) |
| G5 | Final answer / Document answer | builds the Telegram text from data; trims steps to stay under 4000 characters | fixes cut-off messages (F4) |

## Evidence still to collect (to close the before/after requirement)

1. P1, P2, P4: run the hard images of `eval/e2e_tests.md` section C with v1 and with v2 and record the outputs.
2. P3, P5, P6, P7: run the manual tests of section C after importing the v2 workflow.
3. Replace each "not yet measured" above by the observed result. Do not leave a before/after that was not run.
