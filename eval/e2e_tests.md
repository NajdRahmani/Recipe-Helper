# End-to-end tests

## A. Terminal harness (scripts/e2e_test.py, v1)

16 cases (3 text, 3 dish photos, 3 recipe screenshots, 7 ingredient photos): **16/16 passed**.

**Important limit of this result.** The pass criteria were: each agent returns valid JSON, retrieval returns candidates, the Chef answer contains numbered steps. The harness did not check whether the answer was *correct for the input type* (HAVE/MISSING claims, mixed recipes, echoed instructions). The live Telegram tests below found real failures that this harness could not see, so the 16/16 figure measures plumbing, not answer quality. Do not present it as quality.

## B. Live Telegram tests of v1 (7 October 2026), observed failures

| # | Input | What happened | Cause | Fixed in |
|---|---|---|---|---|
| 1 | text: Pizza | answer listed ingredients the user HAD although none were given | Chef invented a HAVE list from the retrieved recipe | Chef v2, then v5 (code computes HAVE/MISSING) |
| 2 | text: Pizza | validator warnings: "only 9 steps, missing 6 and 7" on a 10-step answer | qwen2.5:3b cannot count or compare lists reliably | Validator v3 to v5 |
| 3 | text: Pizza | "recipe may not come from the knowledge base" on a recipe that was in the index | small-model grounding check false positive | rules in code, then v5 |
| 4 | photo: beef, potatoes, carrots, onion, celery, rosemary | detection correct, but several retrieved recipes were pasted together, the MISSING list mixed recipes and the message was cut off | free-text Chef with top-5 context | Chef v3, then v5 |
| 5 | text: chocolate crepes | "HAVE: None" printed and two false check warnings | prompt rule ignored by gemma3:4b; title check broken by an en dash | code guardrail, then v5 |
| 6 | photo: lasagna (dish) | system prompt echoed at the top; guessed ingredients shown as HAVE; "recipe title not found" | echo + dish photo treated as ingredients | Normalize 2, Chef v4, then v5 |
| 7 | any long answer | Telegram 400 "can't parse entities" | Markdown characters from the model | strip characters in code |

Router results in these live tests: ingredient, dish and recipe photos were classified correctly (no misroute observed).

## C. Tests for the v2 workflow (to run after importing it)

Fill the last two columns with what you observe. Do not mark a test as passed without running it.

| # | Input | Expected behaviour | Observed | Pass/Fail |
|---|---|---|---|---|
| 1 | ingredients photo, easy (4 to 6 clear items) | "Detected in your photo", HAVE and MISSING for ONE recipe, few missing, other options listed | | |
| 2 | ingredients photo, dark or blurry | low-confidence items shown as "Not sure about (ignored)", no invented ingredient | | |
| 3 | ingredients photo with caption `vegetarian 30 min` | recipe has the vegetarian tag and is at most 30 min | | |
| 4 | dish photo (lasagna) | "Ingredients needed", steps, NO HAVE/MISSING | | |
| 5 | recipe screenshot | parsed title, ingredients with quantities, steps; NO HAVE/MISSING; no retrieval step | | |
| 6 | text: `I have eggs, tomatoes and cheese` | ingredient path (HAVE/MISSING shown) | | |
| 7 | text: `lasagna` | dish path ("Ingredients needed", no HAVE/MISSING) | | |
| 8 | text (French): `j'ai du poulet, du riz et des oignons` | translated, ingredient path | | |
| 9 | text: `/start` | help message | | |
| 10 | 5 hard router images (screenshot with food, plated dish with raw items around, packaged groceries, handwritten note, empty fridge) | record the Router label for prompt v1 and v2 (before/after) | | |

Pass criteria per mode:
- **ingredient input:** shows HAVE and MISSING, all HAVE items really are in the user's list, steps come from the recipe.
- **dish, recipe screenshot, plain text:** the answer must not contain "You have" or "Missing".
- **all:** one recipe only, message under 4000 characters, no echoed instructions.

Totals (fill in): v1 live tests 0 of 7 clean (all were failures, listed above); v2 live tests: ___ of 10.
