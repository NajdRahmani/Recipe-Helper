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

## C. Live Telegram tests of v2 (12 October 2026)

| # | Input | Expected behaviour | Observed | Pass/Fail |
|---|---|---|---|---|
| 1 | ingredients photo, easy (vegetables: tomato, cucumber, carrot, green beans, broccoli, pepper, sweet potato) | "Detected in your photo", HAVE and MISSING for ONE recipe, few missing, other options listed | "12 hour tomatoes (750 min)". Detected 7 items. HAVE (2 of 3): tomatoes, fresh ground black pepper. Missing (1): cumin seeds. 2 alternatives listed. | PASS |
| 2 | ingredients photo, dark or blurry (fruits with cheese) | low-confidence items shown as "Not sure about (ignored)", no invented ingredient | "Apple a day milk shake (0 min)". Detected: orange, apple, grape, milk, water, tomato. "Not sure about (ignored): cheese". No invented items. | PASS |
| 3 | ingredients photo with caption `vegetarian 30 min` (rice, onion, garlic, chili, tomato, egg, parsley) | recipe has the vegetarian tag and is at most 30 min | "Adriana s mexican rice (30 min)". Time filter applied (30 min). Vegetarian tag not explicitly verified in output. | PARTIAL |
| 4 | dish photo (lasagna) | "Ingredients needed", steps, NO HAVE/MISSING | "10 lb lasagna (180 min)". "Ingredients needed" shown. No HAVE/MISSING. Steps truncated at 12 (message length limit). | PASS |
| 5 | recipe screenshot (chilli con carne) | parsed title, ingredients with quantities, steps; NO HAVE/MISSING; no retrieval step | "Chilli con carne recipe". Full ingredient list with quantities. 6 steps. No HAVE/MISSING. No retrieval. | PASS |
| 6 | text: `I have eggs, tomatoes and cheese` | ingredient path (HAVE/MISSING shown) | "Amazing over easy eggs (10 min)". HAVE (2 of 4): egg, parmesan cheese. Missing (2): ground pepper, rosemary. Substitution suggested. | PASS |
| 7 | text: `lasagna` | dish path ("Ingredients needed", no HAVE/MISSING) | "10 lb lasagna (180 min)". "Ingredients needed" shown. No HAVE/MISSING. | PASS |
| 8 | text (French): `j'ai du poulet, du riz et des oignons` | translated, ingredient path | NOT TESTED | NOT RUN |
| 9 | text: `/start` | help message | "I could not detect any ingredients or request. Send a photo of your ingredients, a photo of a dish, a screenshot of a recipe, or type what you want to cook..." | PASS |
| 10 | text: `hello` | help message or clarification | "Aloha joes (40 min)" — treated as dish name. False positive. | FAIL |
| 11 | text: `chakchouka` | dish path | "Algerian poached eggs chakchouka (30 min)". Correct dish found. | PASS |
| 12 | text: `tunisia` | dish path | "3 layered tunisian tagine (75 min)". Tunisian recipe found. | PASS |
| 13 | text: `apple juice` | ingredient or dish path | "A a a absolutely the cranberry relish (20 min)". Ingredient path with HAVE/MISSING. | PASS |
| 14 | text: `pineapple pie under 60 minutes` | dish path with time filter | "Pink stuff cherry pie filling pineapple dessert (5 min)". Time filter applied but dish name not prioritized. | PARTIAL |
| 15 | unclear photo | helpful error message | "I could not detect any ingredients or request..." | PASS |

**Summary:** 11 PASS, 2 PARTIAL, 1 FAIL, 1 NOT RUN.

**Issues found:**
1. "hello" treated as dish name — Text Intent agent needs greeting detection
2. Time filter works but can override dish name priority
3. Vegetarian tag filter not visible in output (need to verify tag applied)