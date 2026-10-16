# End-to-end tests

## A. Terminal harness (scripts/e2e_test.py, first pipeline)

16 cases (3 text, 3 dish photos, 3 recipe screenshots, 7 ingredient photos): **16/16 passed**.

**Limit of this result.** The harness reproduces the first version of the pipeline. Its pass criteria were: each agent returns valid JSON, retrieval returns candidates, the answer contains numbered steps. It did not check whether the answer was *correct for the input type* (HAVE/MISSING claims, mixed recipes, echoed instructions). The live Telegram tests below found real failures that it could not see, so 16/16 measures plumbing, not answer quality. It does not cover the v3 workflow.

## B. Live Telegram tests of the first versions (7 October 2026): observed failures

| # | Input | What happened | Cause | Fixed in |
|---|---|---|---|---|
| 1 | text: Pizza | answer listed ingredients the user HAD although none were given | Chef invented a HAVE list from the retrieved recipe | Chef v2, then v5 (code computes HAVE/MISSING) |
| 2 | text: Pizza | validator warnings: "only 9 steps, missing 6 and 7" on a 10-step answer | qwen2.5:3b cannot count or compare lists reliably | Validator v3 to v5 |
| 3 | text: Pizza | "recipe may not come from the knowledge base" on a recipe that was in the index | small-model grounding check false positive | rules in code, then v5 |
| 4 | photo: beef, potatoes, carrots, onion, celery, rosemary | detection correct, but several retrieved recipes were pasted together, the MISSING list mixed recipes and the message was cut off | free-text Chef with top-5 context | Chef v3, then v5 |
| 5 | text: chocolate crepes | "HAVE: None" printed and two false check warnings | prompt rule ignored by gemma3:4b; title check broken by an en dash | code guardrail, then v5 |
| 6 | photo: lasagna (dish) | system prompt echoed at the top; guessed ingredients shown as HAVE; "recipe title not found" | echo + dish photo treated as ingredients | Normalize 2, Chef v4, then v5 |
| 7 | any long answer | Telegram 400 "can't parse entities" | Markdown characters from the model | strip characters in code |

Router results in these tests: ingredient, dish and recipe photos were classified correctly (no misroute observed).

## C. Tests for the v3 workflow

Fill the last two columns with what you observe. Do not mark a test as passed without running it.

| # | Input | Expected behaviour | Observed | Pass/Fail |
|---|---|---|---|---|
| 1 | ingredients photo, easy (4 to 6 clear items) | "Detected in your photo", HAVE and MISSING for ONE recipe, few missing, "Other close options" | | |
| 2 | ingredients photo, dark or blurry | low-confidence items shown as "Not sure about (ignored)", no invented ingredient | | |
| 3 | ingredients photo with caption `vegetarian 30 min` | recipe has the vegetarian tag and is at most 30 min; no meat in the substitutions | | |
| 4 | dish photo (lasagna) | "Detected dish", "Ingredients needed", steps, NO HAVE/MISSING | | |
| 5 | recipe screenshot (English) | the user's own recipe (title, ingredient lines, steps), then "Knowledge base (close/partial/loose match)"; NO HAVE/MISSING wording | | |
| 6 | text: `I have eggs, tomatoes and cheese` | ingredient path (HAVE/MISSING shown) | | |
| 7 | text: `lasagna under 40 minutes` | dish path; the recipe is at most 40 min; no HAVE/MISSING | | |
| 8 | text (French): `j'ai du poulet, du riz et des oignons` | translated, ingredient path | | |
| 9 | text (arabizi): `nheb naaml couscous bel lahm` | dish path for couscous; if the corpus has no close recipe the answer says so ("No exact recipe found") | | |
| 10 | 5 hard router images: a screenshot with a food photo, a plated dish with raw items around, packaged groceries, a handwritten recipe note, a menu or price tag | record the Router label for prompt v1 and v3 (before/after) | | |
| 11 | text: `hello`, then `/start` | help message, no recipe | | |
| 12 | image that is not food (selfie, meme, chat screenshot) | polite "does not look like food" reply | | |
| 13 | recipe screenshot in French or Arabic | original text kept in the ingredient lines and steps; search uses the English title | | |
| 14 | cropped or blurry recipe screenshot | warning "Parts of the image were hard to read" | | |

Pass criteria per mode:
- **ingredient input:** shows HAVE and MISSING, all HAVE items really are in the user's list, steps come from the recipe.
- **dish, plain text:** the answer must not contain "You have" or "Missing".
- **recipe screenshot:** shows the user's recipe first; the knowledge-base recipe is labelled as a reference.
- **all:** one recipe only, message under 4000 characters, no echoed instructions.

Totals (fill in): first live tests 0 of 7 clean (all were failures, listed above); v3 live tests: ___ of 14.

## D. Measuring the validator (new in v3)

The Validator now reviews substitutions, intro and tip, and substitutions fail closed. Whether it helps or hurts has to be measured, because the same 3B model was wrong on every earlier kind of check.

1. In n8n open the node **Final answer**, and replace the last line of its code
```javascript
return [{ json: { answer: out, mode: r.mode, chosen: c ? c.name : null, match: r.match, rule_substitutions_kept: subs.length } }];
```
with
```javascript
return [{ json: { answer: out, mode: r.mode, chosen: c ? c.name : null, match: r.match, rule_substitutions_kept: subs.length, subs_proposed: (chef.substitutions || []).length, intro_dropped: !!(chef.intro && !intro), tip_dropped: !!(chef.tip && !tip) } }];
```
2. Run at least 10 requests (ingredient inputs give the most substitutions). Open each run in **Executions**, click **Final answer** and copy the numbers.

| Run | Input | subs_proposed | rule_substitutions_kept | intro_dropped | tip_dropped |
|---|---|---|---|---|---|
| | | | | | |

3. Compute: substitutions kept / proposed, intro drop rate, tip drop rate. Then judge by hand, for each dropped item, whether dropping it was right. A high drop rate of good items means the validator is hurting and "when unsure, answer false" should be relaxed.
