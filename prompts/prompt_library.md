# Prompt library

## P1 Router - v1
Role in system: classify an image as ingredients, a cooked dish, or a recipe document.
Technique: structured JSON output and explicit class definitions.
Prompt: see workflow node `Router`.
Failure cases observed: None in the three text-only terminal E2E cases; image routing was not measured because `eval/images/` is empty.
Fix (-> v2): Not applicable until an image-routing failure is observed.
V1 text: `classify the image with the three explicit type definitions and return JSON`.
V2 text: Not created; preserve v1 until an observed image confusion justifies a change.

## P2 Vision ingredients - v1
Role in system: identify clearly visible food ingredients.
Technique: structured JSON, confidence scores, and an uncertainty list.
Prompt: see workflow node `Vision ingredients`.
Failure cases observed: None observed; no ingredient photos were available.
Fix (-> v2): Not applicable until a hallucinated or partially visible ingredient is observed.
V1 text: `list only clearly visible ingredients, with confidence and uncertain fields`.
V2 text: Not created; preserve v1 until image evidence supports raising the threshold.

## P3 Recipe parser - v1
Role in system: extract written recipe fields from a screenshot or document photo.
Technique: structured JSON plus a copy-only guardrail for quantities and steps.
Prompt: see workflow node `Recipe parser`.
Failure cases observed: None observed; no recipe screenshots were available.
Fix (-> v2): Not applicable until malformed extraction or invented text is observed.
V1 text: `copy only written recipe fields and never invent quantities or steps`.
V2 text: Not created; preserve v1 until document evidence supports an example output.

## P4 Chef - v1
Role in system: produce a concise recipe answer grounded in retrieved candidates.
Technique: role prompting, constrained context, and explicit answer sections.
Prompt: see workflow node `Chef`.
Failure cases observed: No failures in the three text cases; all retrieved five candidates and passed validation.
Fix (-> v2): Not applicable; keep the grounded v1 prompt.
V1 text: `answer with best recipe, HAVE vs MISSING, substitutions, and numbered steps using only candidates`.
V2 text: Not created because v1 produced no observed failure.

## P5 Validator - v1
Role in system: check the Chef response against the user ingredients and retrieved context.
Technique: separate model with structured JSON validation output.
Prompt: see workflow node `Validator`.
Failure cases observed: The direct validator passed all three text cases with valid JSON and no issues. n8n form validation remains unmeasured.
Fix (-> v2): Not applicable until a validator miss is observed.
V1 text: `check HAVE ingredients, non-empty steps, and context grounding; return valid/issues JSON`.
V2 text: Not created because no v1 validator failure was observed.

## Prompt iteration status

The v1 terminal E2E run had 0 failures, so there were no three frequent failures to fix and no evidence-based v2 prompt was created. The image/document v1 run is pending the required input files.

## Final image-test evidence

The first image run reported three document failures, but all three had valid Router and Recipe Parser JSON. Investigation found a harness-only normalization mismatch: `scripts/e2e_test.py` did not fall through from document `{item, quantity}` ingredients to the parsed title. The workflow normalization already had the correct fallthrough. After fixing the harness, the same 16 cases passed 16/16. No real prompt failure was observed, so no v2 prompt change was made.
## P4 Chef - v2
Failure observed (v1): text request "Pizza" (no ingredients provided). The Chef listed a HAVE section copied from the retrieved recipe, claiming the user owned items they never mentioned.
Fix (v2): the prompt receives "NONE PROVIDED" when no ingredients exist and is told to skip HAVE/MISSING and not assume ownership; output is plain text.
Result: <fill in after re-test>

## P5 Validator - v2
Failure observed (v1): the validator flagged every MISSING ingredient as an issue, producing noisy warnings.
Fix (v2): rule (1) only checks HAVE items against the user's list; MISSING lists and substitutions are explicitly allowed.
Result: <fill in after re-test>

## P5 Validator - v3
Failure observed (v2): qwen2.5:3b returned false warnings, e.g. "only 9 steps, missing steps 6 and 7" on a 10-step answer, and "no HAVE list should be included" on an answer with no HAVE list. Small models are unreliable at counting and list comparison.
Fix (v3): deterministic checks (step count, HAVE section without user ingredients) moved into the Final answer code node; the LLM validator is reduced to one task, a grounding check against the retrieved context.
Result: <fill in after re-test>

## P4 Chef - v3
Failure observed (v2): with an ingredients photo (beef, potatoes, carrots, onion, garlic, celery, rosemary) the Chef concatenated several retrieved recipes. The MISSING list mixed ingredients of different recipes (cream of chicken soup, velveeta, bacon) and the message was cut off by the Telegram length limit.
Fix (v3): the prompt forces ONE recipe, forbids mentioning other candidates, and caps MISSING (8), substitutions (3) and steps (8). Build context now sends the top 3 retrieved chunks instead of 5.
Result: <fill in after re-test>

## P2b Vision dish / Normalize 2 - v2
Failure observed (v1): for a dish photo (lasagna) the guessed likely_ingredients were passed as the user's ingredients, so the Chef claimed the user HAD lasagna noodles, ground beef, ricotta.
Fix (v2): a dish photo yields no user ingredients; only the dish name is used as the retrieval query.
Result: <fill in after re-test>

## P4 Chef - v4 (guardrail)
Failure observed (v3): gemma3:4b echoed its system prompt at the top of the answer, which also broke the title check (the first line was the instructions).
Fix (v4): the Final answer node removes echoed instruction paragraphs; the user message ends with "Answer now. Do not repeat these instructions."; apostrophes and dashes are normalised before the title check.
Result: <fill in after re-test>
