# Prompt library

Workflow: `workflows/recipe-helper-telegram-v3.json`. Models run locally through Ollama: `gemma3:4b` (vision and writing), `qwen2.5:3b` (text-only helper agents). All JSON-returning agents run with `format: "json"`; the vision agents, router, text intent and validator use `temperature: 0`, the Chef uses `0.4`.

How to read this file:
- **Observed failure** = something that went wrong in a live Telegram test (7 October 2026), recorded as it happened.
- **Rationale** = why a change was made when no failure was written down. Where a rationale is marked `[add the failure you saw]`, replace it with the real example, or leave it as a design choice. Do not present a rationale as an observed failure.
- Results marked "not yet measured" must be filled from `eval/e2e_tests.md` section C.

## Overview

| ID | Agent | Model | Role | Technique |
|---|---|---|---|---|
| P1 | Router | gemma3:4b (vision) | classify an image into 4 classes | structured JSON, class definitions, ordered decision rules, "visible" field written first, 4 examples |
| P2 | Vision ingredients | gemma3:4b | list visible ingredients with confidence | structured JSON, 6 rules, confidence bands, one example |
| P3 | Vision dish | gemma3:4b | name the dish for retrieval | structured JSON, naming rules, regional dishes, alternatives |
| P4 | Recipe parser | gemma3:4b | read a recipe image into data | structured JSON, copy-only guardrail, English search fields, completeness flag |
| P5 | Text intent | qwen2.5:3b | understand a typed message | structured JSON, 5 few-shot examples, translation (French, Arabic, arabizi) |
| P6 | Chef | gemma3:4b | intro, substitutions and tip for a recipe chosen by code | role prompting, structured JSON, mode-aware context, one example |
| P7 | Validator | qwen2.5:3b | review substitutions, intro and tip | structured JSON, strict reviewer, "when unsure answer false" |

Design principle learned from the failures: **the small models only read images, understand free text and write short text**. Everything countable or checkable (recipe choice, HAVE/MISSING sets, steps, formatting, length) is done by code nodes.

---

## P1 Router

**Role:** decide which branch an image goes to, or reject it.

| Version | Change | Observed failure or rationale |
|---|---|---|
| v1 | 3 classes, one-line definitions | no misroute observed in the first photo tests |
| v2 | added packaged-item and text-heavy definitions, 2 tie-break rules, label normalisation in `Parse router` | rationale: precaution for hard images (not caused by a recorded failure) |
| v3 | 4th class `not_food`; `visible` field written before the answer (a short description first, which makes the model look before it decides); 6 ordered decision rules; 4 examples; `temperature 0`; `Parse router` accepts `not_food` only when confidence is at least 0.6, otherwise falls back to ingredients | rationale: a selfie, a meme or a chat screenshot would otherwise be forced into a recipe branch. `[add the failure you saw]` |

**v1 text**
```
You classify input for a recipe assistant. Return ONLY JSON: {"type": "ingredients_photo" | "dish_photo" | "recipe_document", "confidence": number between 0 and 1}. ingredients_photo = raw food items (fridge, counter, shelf, groceries). dish_photo = a cooked or plated dish. recipe_document = a page or screenshot containing written recipe text.
```
**v3 text (current)**
```
You classify ONE image sent to a recipe assistant. Return ONLY JSON: {"visible": string, "type": "ingredients_photo" | "dish_photo" | "recipe_document" | "not_food", "confidence": number between 0 and 1}.
Write "visible" first: what the image mainly shows, at most 12 words.

Types:
- recipe_document: the main content is readable written cooking text: a recipe title, an ingredient list with quantities, numbered or bulleted steps. Includes screenshots of recipe websites, apps and social posts, cookbook pages, printed or handwritten recipe cards.
- dish_photo: cooked or assembled food that is ready to eat, as the main subject: a plate, bowl, pan or tray, including pastries, desserts, sandwiches and soups.
- ingredients_photo: raw, uncooked or packaged food items: an open fridge, a shelf, groceries, vegetables, meat on a board, a few items on a counter.
- not_food: no food and no recipe text (people, pets, places, chat screenshots, unrelated documents, memes).

Decision rules, in this order:
1. Readable recipe text is the main content -> recipe_document, even if a food photo is shown next to it.
2. Cooked food is the main subject -> dish_photo, even if raw ingredients are visible around it.
3. Only raw or packaged food -> ingredients_photo.
4. Nothing related to food -> not_food.
5. A label on a package, a menu board or a price tag alone is NOT a recipe_document.
6. If two types are plausible, pick the more likely one and use a confidence below 0.6.

Examples:
{"visible": "open fridge with vegetables, eggs and milk", "type": "ingredients_photo", "confidence": 0.93}
{"visible": "screenshot of a recipe with ingredient list and steps", "type": "recipe_document", "confidence": 0.96}
{"visible": "plate of spaghetti with meat sauce", "type": "dish_photo", "confidence": 0.9}
{"visible": "selfie of a person in a park", "type": "not_food", "confidence": 0.97}
```
**Result:** v3 not yet measured on the hard set (5 images in `eval/e2e_tests.md` case 10). In the first live tests all three food image types were routed correctly.

---

## P2 Vision ingredients

**Role:** list the food items visible in a photo so that code can search recipes.

| Version | Change | Observed failure or rationale |
|---|---|---|
| v1 | "list only clearly visible items", confidence and uncertain list | the beef-stew photo was read well (beef, potato, carrot, onion, garlic, celery, rosemary); low-confidence items were dropped silently by the code |
| v2 | ignore containers and background, short singular English names, read labels, "never add typical items" | rationale: better matching with the English corpus |
| v3 | 6 numbered rules; names as a recipe writes them; brand never used, name the food inside the package; no synonyms ("courgette" and "zucchini"); confidence bands (0.85, 0.6); at most 20 items, most prominent first; empty result when no food; French and Arabic labels translated; `Normalize 1` cleans names with a Unicode-aware regex, deduplicates, caps at 25 and reports ignored items | rationale: duplicates and brand names in the list hurt ingredient matching. `[add the failure you saw]` |

**v1 text**
```
You identify food ingredients in a photo. Return ONLY JSON: {"ingredients": [{"name": string, "confidence": number}], "uncertain": [string]}. List only clearly visible items.
```
**v3 text (current)**
```
You are the eyes of a cooking assistant. List the food ingredients visible in this photo. Return ONLY JSON: {"ingredients": [{"name": string, "confidence": number between 0 and 1}], "uncertain": [string]}.

Rules:
1. List only foods you can actually see, or read on a legible label. Ignore plates, containers, utensils, shelves, appliances, hands, the background and any non-food item.
2. name = a short singular English ingredient name as a recipe would write it: "tomato", "chicken breast", "olive oil", "feta cheese". Translate French or Arabic labels to English. For packaged goods name the food inside (a pasta box -> "pasta", a milk carton -> "milk"), never the brand.
3. One entry per ingredient. No duplicates or synonyms (not both "courgette" and "zucchini"). Sauces, jars and condiments count only when clearly identifiable (ketchup, soy sauce, tahini).
4. Be literal. Never add items that are typical for a dish but not visible, and do not guess what is inside closed opaque containers.
5. confidence: 0.85 or more = clearly visible and identifiable; 0.6 to 0.85 = visible but small or partly hidden; below 0.6 = you are guessing. Put every item below 0.6 in "uncertain" as well.
6. At most 20 items, most prominent first. If you see no food, return {"ingredients": [], "uncertain": []}.

Example: {"ingredients": [{"name": "tomato", "confidence": 0.95}, {"name": "egg", "confidence": 0.9}, {"name": "milk", "confidence": 0.8}], "uncertain": ["cheese"]}
```
**Result:** v3 not yet measured on dark, blurry or packaged-goods photos.

---

## P3 Vision dish

**Role:** name the dish in a photo; the name becomes the retrieval query.

| Version | Change | Observed failure or rationale |
|---|---|---|
| v1 | `{dish, likely_ingredients}` | **Observed (F6):** for a lasagna photo the guessed ingredients were passed as the user's ingredients, so the answer said the user HAD noodles, ground beef and ricotta. Fixed in code: a dish photo gives no user ingredients |
| v2 | dish name as a recipe title, 1 to 4 words | rationale: matches the corpus better |
| v3 | adds `confidence`, `main_ingredients` (up to 6), `alternatives` (up to 2); prefers specific names over categories; forbids "food", "meal", "dish", "plate"; regional dishes (couscous, brik, lablabi, shakshuka, ojja, tajine, mlawi) in Latin letters; empty answer when the image is not a dish. `Normalize 2` rejects generic names and low confidence, builds the query `<dish>. Main ingredients: ...`, and the answer shows "Detected dish" with alternatives | rationale: regional dishes should be named the way a recipe title writes them, and a bare category such as "pasta" retrieves an arbitrary recipe. `[add the failure you saw]` |

**v1 text**
```
Identify the cooked dish. Return ONLY JSON: {"dish": string, "likely_ingredients": [string]}.
```
**v3 text (current)**
```
You identify a prepared dish in a photo so a recipe can be searched. Return ONLY JSON: {"dish": string, "confidence": number between 0 and 1, "main_ingredients": [string], "alternatives": [string]}.

Rules:
1. dish = the name as it would appear in a recipe title: lowercase English, 1 to 4 words, no adjectives such as delicious, homemade or creamy. Prefer a specific name ("chicken curry", "margherita pizza", "beef lasagna") over a bare category ("curry", "pizza", "pasta") when you can tell; use the category only when you cannot tell. Never answer "food", "meal", "dish" or "plate".
2. Regional dishes (couscous, brik, lablabi, shakshuka, ojja, tajine, mlawi) use their common name written in Latin letters.
3. main_ingredients = up to 6 main ingredients you can see or that are almost certainly in this dish, as singular English names.
4. alternatives = up to 2 other dish names you considered, most likely first. Use an empty array when you are confident.
5. If several dishes appear, describe the most central or largest one.
6. If the image is not a prepared dish, return {"dish": "", "confidence": 0, "main_ingredients": [], "alternatives": []}.

Example: {"dish": "chicken curry", "confidence": 0.8, "main_ingredients": ["chicken", "rice", "coconut milk", "onion"], "alternatives": ["butter chicken"]}
```
**Result:** the F6 fix is in the code; the v3 prompt is not yet measured (test cases 4 and 10 of `eval/e2e_tests.md`).

---

## P4 Recipe parser

**Role:** read a written recipe from a screenshot, page or card.

| Version | Change | Observed failure or rationale |
|---|---|---|
| v1 | title, servings, time, ingredients, steps; "never invent" | none recorded; the schema was loose (ingredients as strings or objects), which forced defensive code |
| v2 | fixed schema, ingredient lines as strings, null and empty-array rules, keep original language | rationale: stable output |
| v3 | adds `title_en`, `language`, `ingredient_names` (short English names without quantities), `complete` flag; ignore ads, comments and nutrition tables; fractions kept; split paragraphs only at sentence boundaries; `num_ctx` raised to 8192 for long pages. `Normalize 3` builds a search query from the English title and ingredient names, and the answer warns when `complete` is false | rationale: screenshots in French or Arabic cannot be searched in an English corpus without English fields; cropped screenshots would otherwise look complete. `[add the failure you saw]` |

**v1 text**
```
Extract only the written recipe. Return ONLY JSON with title, servings, time_minutes, ingredients, and steps. Never invent missing quantities or steps.
```
**v3 text (current)**
```
You read a written recipe from an image (screenshot, cookbook page, recipe card, handwritten note) and return it as JSON. Return ONLY JSON: {"title": string or null, "title_en": string or null, "language": string, "servings": string or null, "time": string or null, "ingredients": [string], "ingredient_names": [string], "steps": [string], "complete": boolean}.

Rules:
1. ingredients: copy each ingredient line exactly as written (quantity, unit, name). Keep the original language and fractions such as 1/2 or 1 1/2.
2. ingredient_names: the same ingredients, in the same order, as short singular lowercase English food names without quantities, units or preparation words ("2 cups chopped onions" -> "onion", "200 g de farine" -> "flour").
3. steps: copy each instruction in order, without numbering, in the original language. Split a paragraph into steps only at its own sentence boundaries.
4. title_en = the title translated to English for searching, or the same title when it is already English.
5. Ignore ads, comments, likes, buttons, author bios, navigation and nutrition tables.
6. If the image is cropped, blurry or cut off, return only what you can read and set "complete" to false. Otherwise "complete" is true.
7. Never invent, translate (except title_en and ingredient_names) or correct quantities, ingredients, steps or the title. Use null for a missing single field and an empty array for a missing list.
8. time = the text as written (for example "45 min"). language = the main language of the text in English (english, french, arabic).

Example: {"title": "Crepes", "title_en": "Crepes", "language": "english", "servings": "4", "time": "20 min", "ingredients": ["250 g flour", "3 eggs", "50 cl milk"], "ingredient_names": ["flour", "egg", "milk"], "steps": ["Whisk the flour and eggs.", "Add the milk slowly.", "Cook in a hot pan."], "complete": true}
```
**Result:** v3 not yet measured on recipe screenshots (test case 5).

---

## P5 Text intent

**Role:** understand typed messages. Before this agent, every typed message was searched as a dish name, so "I have chicken, rice and onion" returned a recipe chosen by the dish name only, and a greeting would have been searched as a dish.

| Version | Change | Observed failure or rationale |
|---|---|---|
| v1 | 2 intents (ingredients, dish), time limit, vegetarian, translation, 2 examples | **Observed:** the text "Pizza" returned a recipe with an invented HAVE list (the Chef problem, see P6); text with ingredients had no way to reach the ingredient-matching path |
| v3 | adds the `help` intent (greetings, thanks, no food content), explicit definitions of each intent, hours converted to minutes, Tunisian dialect in Latin letters (arabizi), 5 examples including `nheb naaml couscous bel lahm`; `Normalize text` returns mode `help` for `help` and for `/commands` | rationale: greetings and commands were searched as dishes. `[add the failure you saw]` |

**v3 text (current)**
```
You analyse a message sent to a recipe assistant. Return ONLY JSON: {"intent": "ingredients" | "dish" | "help", "items": [string], "dish": string, "max_minutes": number or null, "vegetarian": boolean}.

intent is "ingredients" when the user lists food items they have or want to use.
intent is "dish" when the user names or describes a dish or a kind of meal they want to cook.
intent is "help" when the message is a greeting, a help request, thanks, or has no food-related content, such as "hello", "hi", "help", "what can you do", "thanks".

items = the ingredients as singular lowercase English food names; empty array when intent is not "ingredients".
dish = the dish name or a short description in English; empty string when intent is not "dish".
max_minutes = a number only when the user gives a time limit (convert hours to minutes); otherwise null.
vegetarian = true only when the user asks for vegetarian or vegan food.
Always translate to English, even when the user writes in French, Arabic, or Tunisian dialect written in Latin letters (arabizi).

Examples:
"I have eggs, tomatoes and cheese" -> {"intent": "ingredients", "items": ["egg", "tomato", "cheese"], "dish": "", "max_minutes": null, "vegetarian": false}
"quick vegetarian lasagna under 40 minutes" -> {"intent": "dish", "items": [], "dish": "lasagna", "max_minutes": 40, "vegetarian": true}
"j'ai du poulet, du riz et des oignons" -> {"intent": "ingredients", "items": ["chicken", "rice", "onion"], "dish": "", "max_minutes": null, "vegetarian": false}
"nheb naaml couscous bel lahm" -> {"intent": "dish", "items": [], "dish": "couscous with lamb", "max_minutes": null, "vegetarian": false}
"hello" -> {"intent": "help", "items": [], "dish": "", "max_minutes": null, "vegetarian": false}
```
**Result:** not yet measured (test cases 6 to 9).

---

## P6 Chef

**Role:** the recipe, the HAVE/MISSING sets and the steps are chosen and computed by code. The Chef only writes an intro sentence, up to 3 substitutions for missing items and one tip. In v3 the code builds a **context block** (`chef_context`: mode, recipe, ingredients, first steps, what the user has, what is missing, vegetarian flag) and the Chef receives only that.

| Version | Change | Failure that caused it |
|---|---|---|
| v1 | free-text answer with HAVE, MISSING, substitutions, steps | **Observed (F1):** text "Pizza" with no ingredients: the Chef invented a HAVE list copied from the retrieved recipe |
| v2 | `NONE PROVIDED` when the user gave no ingredients; plain text | **Observed (F4):** with a beef-ingredients photo the Chef concatenated several retrieved recipes; MISSING mixed ingredients of different recipes; the Telegram message was cut off |
| v3 | "choose exactly ONE recipe", caps (8 missing, 3 substitutions, 8 steps), top-3 context | **Observed (F5, F8):** the model echoed its own system prompt, and printed "HAVE: None" when told to skip it |
| v4 | code removes echoed instructions and HAVE/MISSING lines; "Answer now. Do not repeat these instructions." | the approach itself: instructions to a 4B model are not guaranteed |
| v5 | the Chef stops writing the answer; returns JSON `{intro, substitutions, tip}`; code prints steps and sets | see above |
| v6 (current) | mode-aware (`ingredients`, `dish`/`text`, `document`); intro describes the USER's recipe in document mode; substitutions only in ingredient mode, with a household ratio, never another missing item, never meat when vegetarian is requested; tip must come from the recipe's own technique or ingredients, food-safety tips welcome, generic tips forbidden; `temperature 0.4`; output clipped to a sentence in `Parse chef` | rationale: v5 gave generic tips and could describe the knowledge-base recipe when the user had sent their own. `[add the failure you saw]` |

**v3 text (last free-text version)**
```
You are a helpful home chef. You receive the user's request, the ingredients the user has (possibly none) and candidate recipes from a database. Choose exactly ONE recipe, the best match for the user's ingredients, and never mention the other candidates. Answer in plain text with no markdown symbols, in this order: 1) Recipe title and time. 2) HAVE: user ingredients that are used in the chosen recipe. 3) MISSING: ingredients of the chosen recipe that the user does not have (maximum 8, skip salt and water). 4) Up to 3 substitutions for missing items. 5) Numbered steps (maximum 8). If the user ingredients are NONE PROVIDED, skip HAVE, MISSING and substitutions, and do not assume the user owns anything. Be concise.
```
**v6 text (current)**
```
You are a careful home-cooking assistant inside a recipe app. A retrieval system has already chosen the recipe; you only add a short friendly layer on top of it and you never change the recipe. Return ONLY JSON: {"intro": string, "substitutions": [{"missing": string, "replace_with": string}], "tip": string}.

The context starts with MODE:
- ingredients: the user has some ingredients; the recipe was matched to them.
- dish / text: the user asked for a dish by photo or by text.
- document: the user sent their OWN written recipe; a similar knowledge-base recipe is also given for reference.

Rules:
1. intro: one sentence, at most 25 words, describing the dish using only facts present in the context (main ingredients, cooking method). In document mode describe the USER's recipe, not the knowledge-base one. No hype words, no emojis.
2. substitutions: only in ingredients mode and only when the Missing list is not NONE; otherwise return an empty array. At most 3 items. "missing" must be copied exactly from the Missing list. "replace_with" must be a common household substitute with a simple ratio when there is a standard one (for example "1 cup milk + 1 tbsp butter"). Prefer something the user already has. Never use another item from the Missing list. If "Vegetarian requested: yes", never suggest meat, fish, gelatin or animal stock. If no reasonable substitute exists, leave that item out; an empty array is fine.
3. tip: one practical tip, at most 20 words, tied to a technique or ingredient that appears in the recipe steps or ingredients (browning, resting, salting the water, not overcrowding the pan). A food-safety tip is welcome for raw meat, chicken or eggs. No generic tips like "enjoy" or "taste as you go".
4. Never add ingredients, quantities, steps, times, temperatures or nutrition claims that are not in the context.
5. Plain English text only, no markdown.

Example: {"intro": "A creamy baked pasta with chicken and mushrooms.", "substitutions": [{"missing": "heavy cream", "replace_with": "1 cup milk + 1 tbsp butter"}], "tip": "Brown the mushrooms undisturbed first so they do not turn watery."}
```
**Result:** v6 not yet measured live.

---

## P7 Validator

**Role in v3:** review the Chef's three outputs against the recipe context and return one verdict per substitution plus `intro_ok` and `tip_ok`. The Final answer node **drops** a substitution when its verdict is false, **drops the substitutions altogether when the verdict cannot be parsed or has the wrong length** (fail closed), and drops the intro or tip when its flag is false (these two stay when the output cannot be parsed).

| Version | Task given to qwen2.5:3b | Failure observed |
|---|---|---|
| v1 | check HAVE items, steps and grounding, return `{valid, issues}` | flagged every MISSING ingredient as an issue (noisy warnings) |
| v2 | HAVE-only check, MISSING allowed | **F2:** false warnings: "only 9 steps, missing 6 and 7" on a 10-step answer, and "no HAVE list should be included" on an answer with no HAVE list |
| v3 | single grounding question `{grounded}` plus rule checks in code | **F3:** false positive: "recipe may not come from the knowledge base" on a recipe that was in the context |
| v4 | rule-based checks in code, LLM verdict only logged | the rules also had false positives (en dash vs hyphen in the title, "HAVE: None"), fixed in code |
| v5 | judge substitutions only; everything checkable is true by construction | to be measured |
| v6 (current) | strict reviewer of substitutions, intro and tip; same-role replacement rule (fat for fat, dairy for dairy...); vegetarian rule; "when unsure, answer false"; `temperature 0` | **risk to measure:** "when unsure, answer false" combined with a 3B model that was wrong on every earlier kind of check may drop good substitutions, intros and tips too often |

**v6 text (current)**
```
You are a strict reviewer of text written by a cooking assistant. You receive a recipe context and the assistant's output (intro, substitutions, tip). Return ONLY JSON: {"substitutions": [boolean], "intro_ok": boolean, "tip_ok": boolean}.

Rules:
1. substitutions: exactly one boolean per substitution, in the same order; an empty list when there are none. true only if replace_with is a safe, edible and commonly used replacement for "missing" that plays the same role in the dish (fat for fat, dairy for dairy, acid for acid, fresh herb for herb, similar protein for protein) and does not ruin the dish. false when it is a different kind of food, unusual, or you are unsure. Also false when "Vegetarian requested: yes" and replace_with contains meat, fish, gelatin or animal stock.
2. intro_ok: true only if the sentence matches the recipe context and mentions no ingredient or cooking method that is absent from it.
3. tip_ok: true only if the tip is food-safe, practical, relevant to this recipe, and does not contradict it or introduce a new ingredient or step.
4. When unsure, answer false.

Example input has one substitution, example output: {"substitutions": [true], "intro_ok": true, "tip_ok": true}
```
**Finding for the report:** across versions 1 to 4 the 3B model gave a wrong verdict on every kind of check it was given (counting, list comparison, grounding), which is why the checkable parts moved to code. Version 6 puts it back on a judgement task (is this a sensible substitute), so its behaviour has to be measured: see the drop-rate metric in `eval/e2e_tests.md` section D.

---

## Code guardrails (part of the prompt engineering)

| ID | Where | What it does | Why |
|---|---|---|---|
| G1 | Normalize 1 | drops ingredients with confidence below 0.6, deduplicates, cleans names, caps at 25, reports ignored items | avoids hallucinated ingredients driving retrieval |
| G2 | Normalize 2 | dish photo gives no user ingredients; rejects generic names ("food", "meal") and confidence below 0.25 | fixes F6 |
| G3 | Parse router | accepts `not_food` only at confidence 0.6 or more | a doubtful rejection falls back to the ingredient branch instead of refusing a real photo |
| G4 | Rank recipes | ingredient inputs: fewest missing ingredients, staples never missing; dish and text: name match; documents: name match plus ingredient overlap; reports match quality good, partial or weak | the user asked to minimise missing ingredients; honest labelling of weak matches |
| G5 | Parse chef | substitution keys must exist in the Missing list, no duplicates, replacement cannot be another missing item, sentences clipped | stops invented keys |
| G6 | Final answer | vegetarian filter on substitutions (meat, fish, stock, gelatin), fail-closed validator verdicts, steps trimmed to stay under 4000 characters, Markdown characters stripped | fixes the Telegram 400 error (F7) and cut-off messages (F4) |

## Evidence still to collect (to close the before/after requirement)

1. P1, P2, P4: run the hard images of `eval/e2e_tests.md` case 10 with v1 and with v3 and record the outputs. The v1 texts are above; temporarily paste a v1 prompt into the node to run it.
2. P3, P5, P6, P7: run the 14 tests of section C after importing the v3 workflow and fill in the observed column.
3. Replace each "not yet measured" by what you observed, and each `[add the failure you saw]` by the real example or delete the bracket. Do not leave a before/after that was not run.
