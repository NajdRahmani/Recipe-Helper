# Recipe Helper: multimodal, multi-agent recipe assistant

Advanced Deep Learning, final project (AI automation). Everything runs locally: n8n, Ollama (`gemma3:4b`, `qwen2.5:3b`, `bge-m3`) and Qdrant in Docker. The user talks to a Telegram bot. No API cost, no fine-tuning.

## 1. Use case and architecture

The user sends one of four things: a **photo of ingredients**, a **photo of a cooked dish**, a **screenshot of a recipe**, or **text** (a list of ingredients, a dish name, French or Arabic allowed). The answer depends on the input type:

| Input | What the user gets |
|---|---|
| ingredients (photo or text) | the recipe that **needs the fewest extra ingredients**, with "You have" and "Missing", substitutions, steps, and two other close options |
| dish photo or dish name | the recipe with "Ingredients needed" and steps, **no have/missing** (the user has not said what they own) |
| recipe screenshot | the recipe as extracted from the image (ingredients with quantities, steps), no have/missing |

![architecture](architecture.png)

Pipeline: Telegram trigger, progress message, input switch. Images are downloaded, converted to base64 and classified by the **Router**. A vision agent (ingredients, dish or recipe parser) produces JSON, and a **Normalize** node turns every input into the same contract `{mode, query, user_ingredients, filters}`. Retrieval embeds the query with `bge-m3` and searches Qdrant. A code node **ranks** the candidates, the **Chef** agent adds an intro, substitutions and a tip, the **Validator** agent checks the substitutions, and a code node builds the Telegram message. Recipe screenshots skip retrieval.

n8n workflow: `workflows/recipe-helper-telegram-v2.json`, 30 nodes, started by a Telegram message (end to end, no manual step).

## 2. Prompt engineering

Seven prompts are versioned in `prompts/prompt_library.md` (role, technique, text of each version, failure, fix). Techniques used: structured JSON output, role prompting, few-shot examples (text intent, chef, ingredient vision), explicit class definitions with tie-break rules (router), guardrails ("only clearly visible", "copy only what is written"), confidence thresholds, translation to English, and **code-level guardrails** around the model.

Main iteration, measured on live Telegram tests (7 October 2026). Seven real failures were found in the live tests and fixed (full table in `eval/e2e_tests.md`, section B); the main groups:

| Failure | Before | After |
|---|---|---|
| Chef invented a HAVE list when the user gave no ingredients | v1 free text | v2: `NONE PROVIDED`, then v5: HAVE/MISSING computed by code |
| Chef merged several retrieved recipes, message cut off | v2 | v3: one recipe, caps, top-3; v5: one recipe chosen by code |
| Chef echoed its system prompt, printed "HAVE: None" | v3 | v4 code cleanup; v5 the Chef returns JSON only |
| Validator (3B) gave false warnings on three different checks | v1 to v3 | v4 rules in code; v5 the LLM only judges substitutions, fail-open |
| Dish photo: guessed ingredients treated as owned | v1 | Normalize 2 yields no user ingredients |
| Telegram rejected Markdown characters | v1 | stripped in code |

**Lesson.** A 4B model does not reliably follow "skip this section" or count steps. Anything that can be computed (sets, counts, formatting, length) moved into code, and the model only does reading and writing. This is also why the harness result (16/16) is reported as plumbing only.

Prompts whose v2 has not been measured yet are marked "not yet measured" in the library; the before/after for the Router, ingredient vision and recipe parser is collected with the hard-image set of `eval/e2e_tests.md` section C. [FILL: results]

## 3. RAG

**Corpus.** Food.com recipes (`RAW_recipes.csv`, more than 180,000 recipes). We index the first 6,000 usable recipes (at least 3 ingredients and 2 steps). Structured CSV with name, ingredients, steps, minutes and tags, which suits both ingredient matching and filtering. The size is a compromise: a larger corpus gives better matches for the "fewest missing ingredients" goal, but indexing on CPU takes minutes per few thousand recipes.

**Three chunking strategies compared** (same embedding model and store):

| Collection | Chunking | Points |
|---|---|---|
| `recipes_fixed` | whole recipe text cut in windows of 800 characters, 100 overlap, first 2,000 recipes | 2,832 |
| `recipes_struct` | two chunks per recipe (ingredients, steps), each prefixed with title and tags, first 2,000 recipes | 4,000 |
| `recipes_rich` | **one chunk per recipe**: "name. Ingredients: ..." is embedded; the full recipe (ingredient list, steps, minutes, tags) is stored in the payload | about 6,000 |

Why `recipes_rich`: the first two collections store only text, so the system could not know which ingredients a recipe needs without parsing text. With a recipe-level chunk and structured payload, code can compute missing ingredients exactly and print the recipe's own steps. The embedded text focuses on name and ingredients, which is what both dish names and ingredient lists look like.

**Embedding and store.** `bge-m3` (1024 dimensions, multilingual, local) and Qdrant with cosine distance, payload indexes on `minutes` and `tags`.

**Retrieval setup.**
- dish, text and document queries: top-5, then a small rerank that prefers recipes whose name contains the query words;
- ingredient queries: **top-40, then rerank by code**: recipes must use at least 2 of the user's ingredients and have at least 3 needed ingredients; sorted by fewest missing ingredients, then most user ingredients used, then vector score. Salt, pepper, water, oil and sugar never count as missing. Matching is token-based with simple singularisation (tomatoes matches tomato, chicken matches boneless chicken breasts);
- metadata filters: `minutes <= N` and the `vegetarian` tag, filled from the text ("under 30 minutes") or the photo caption.

**Evaluation 1: dish-name retrieval** (10 queries, `eval/queries.csv`, loose descriptions of known recipes):

| Collection | k | Hit@k | MRR |
|---|---:|---:|---:|
| recipes_fixed | 3 | 0.90 | 0.75 |
| recipes_fixed | 5 | 0.90 | 0.75 |
| recipes_fixed | 10 | 1.00 | 0.76 |
| recipes_struct | 3 | 0.90 | 0.68 |
| recipes_struct | 5 | 0.90 | 0.68 |
| recipes_struct | 10 | 1.00 | 0.70 |
| recipes_rich | 3 / 5 / 10 | [FILL: run `python scripts/eval.py`] | |

Reading: fixed chunking ranked the expected recipe higher than structured chunking (MRR 0.75 against 0.68). Our hypothesis, not tested, is that the structured strategy uses two slots per recipe in the top-k. The set has 10 queries, so a difference of 0.07 is about one query and is directional only. Note that `recipes_rich` searches a corpus three times larger than the other two, which makes the same queries harder.

**Evaluation 2: ingredient matching** (`scripts/eval_ingredients.py`). Simulated users: 40 recipes are picked, the user "owns" 70% of the recipe's ingredients, and we compare the top-1 recipe of plain vector search with the top-1 after reranking, with the source recipe removed from the candidates. Metrics: average number of missing ingredients, share of cases with at most 2 missing, share of the user's ingredients that the recipe uses.

| Method | Avg missing | Missing <= 2 | User ingredients used |
|---|---|---|---|
| vector top-1 | [FILL] | [FILL] | [FILL] |
| top-40 + rerank | [FILL] | [FILL] | [FILL] |

Limit: the simulated users name ingredients exactly as the corpus does ("boneless skinless chicken breasts"), while real users and the vision model say "chicken". The matching code handles the second case (unit-tested), but the numbers above are an upper bound.

## 4. Multi-agent system

| Agent | Model | Tools | Input | Output |
|---|---|---|---|---|
| Router | gemma3:4b (vision) | none | image | type, confidence |
| Vision ingredients | gemma3:4b | none | image | ingredients with confidence |
| Vision dish | gemma3:4b | none | image | dish name |
| Recipe parser | gemma3:4b | none | image | title, ingredient lines, steps |
| Text intent | qwen2.5:3b | none | message | ingredients or dish, time limit, vegetarian, English |
| Retrieval + rank | bge-m3, Qdrant, code | vector search, filters, ranking code | query, filters | one recipe, HAVE, MISSING, alternatives |
| Chef | gemma3:4b | none | chosen recipe, have, missing | intro, substitutions, tip |
| Validator | qwen2.5:3b | none | substitutions | one verdict per substitution |

**Architecture: router plus sequential chain with branches**, orchestrated by n8n. The Router and the Text-intent agent choose the branch; the rest is a fixed chain. Information flows through one contract (`mode`, `query`, `user_ingredients`, `filters`), which is why the answer format can change per input type without changing the agents.

**Why not one prompt.** The same 4B model would have to classify, read an image, retrieve, choose, compute and write. Our failures show it does one of these at a time at best, and separate agents let us fix one prompt without breaking the others (the Chef went through five versions while the vision agents needed no change in the live tests).

**Why not a tool-calling agent loop or a hierarchy.** Small local models call tools unreliably, and every extra model call costs minutes on CPU. A deterministic chain is predictable, debuggable in n8n's execution view and cheap. The price is that agents do not decide their own steps; only the Router and Text-intent agents decide a branch, and we state that openly.

**Why code in the chain.** The first design let the Chef write HAVE/MISSING and the Validator check it. Both failed repeatedly (section 2), so choosing the recipe, computing the sets and building the message moved to code, which makes those parts correct by construction.

## 5. Multimodality

Photos arrive from Telegram, are downloaded and base64-encoded, and are read by `gemma3:4b` through Ollama. Four tasks use the image: classification (Router), ingredient extraction, dish naming and recipe extraction (OCR with layout understanding of a screenshot). What it brings: the user does not type ingredients; a photo of a fridge becomes a ranked list of cookable recipes; a screenshot of a recipe is turned into clean structured text; a dish photo becomes a recipe. The caption of a photo can add `vegetarian` or a time limit. Text input is multilingual (French, Arabic, Tunisian dialect) through the Text-intent agent.

## 6. Failed attempts and limits

- **LLM as validator.** `qwen2.5:3b` gave a wrong verdict on counting, list comparison and grounding. Replaced by code; the LLM now judges only substitutions and fails open.
- **Chef writes the whole answer.** Invented HAVE lists, merged recipes, echoed its prompt. Replaced by code-built answers.
- **Harness vs reality.** The terminal harness reported 16/16 while live tests found seven failures; its criteria were too weak.
- **Telegram.** Markdown parse errors from model output; the progress message ran last because n8n executes the upper branch first (fixed by wiring order).
- **Limits.** 10 retrieval queries; recipe screenshots and hard photos tested on a small set; corpus of 6,000 recipes; no reranker model; CPU latency of several minutes per image; the public tunnel URL changes at each restart; no fine-tuning (the failures were fixed with prompts and code; a LoRA fine-tune of the vision model on labelled fridge photos would be the next step).

## Files

`workflows/recipe-helper-telegram-v2.json`, `scripts/` (`index.py`, `index_rich.py`, `eval.py`, `eval_ingredients.py`, `ranker.py`, `e2e_test.py`), `prompts/prompt_library.md`, `eval/` (queries, results, e2e tests), `report/` (this file and the diagram).
