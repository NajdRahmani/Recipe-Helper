# Recipe Helper — Universal multimodal agent prompts

## Purpose

This is a **general-purpose** revision of the existing 25-node, 3-embedded-tool-workflow n8n Recipe Helper workflow. A refrigerator is **one possible source image**, not an architectural assumption. The assistant supports text requests, photos of raw ingredients in any location, finished dishes, screenshots/photographs of written recipes, and text combined with photographs.

The purpose of this update is to improve **observational accuracy and ingredient-aware recipe selection** without retraining or changing the fine-tuned Ollama model `recipe-intent-lora:latest`.

## Changed

| Component | Changes |
|---|---|
| Image Router | Detailed, general categorization of photographed ingredients, a prepared dish, a written recipe, or unrelated imagery. Explicit ambiguity policies. |
| Vision ingredients | Thorough spatial scanning of any food arrangement (counter, pantry, grocery haul, fridge, market, freezer, etc.), visual evidence and confidence, no speculative ingredients. |
| Vision verify inventory | Independent second pass checks the original image, removes unsupported ingredients and adds clearly visible missed ones. |
| Vision dish | Names only visually plausible prepared dishes; distinguishes observed ingredients from culturally typical but unseen ingredients. |
| Recipe parser | Source-faithful multilingual written-recipe extraction, careful reading order, no invented quantities or instructions. |
| Supervisor AI Agent | Expanded tool-by-tool orchestration instructions and behavior for each normalized request mode. Bounded tool calls, unchanged final approval gate. |
| Search tool | General ingredient-conditioned retrieval rather than refrigerator-specific or soup-specific search phrases. UI filters retained. |
| Rank + Chef tool | Existing coverage-based ranking retained for any known ingredient inventory; Chef instructed not to add or claim ingredients not present in the selected recipe. |
| Validator | Detailed independent checks against the exact KB recipe or original uploaded document, stricter grounding of Chef notes and substitution evidence. |

**Unchanged:** 25 main nodes, all original main-node IDs, connection topology, embedded tool sub-workflow counts, fine-tuned text-intent node, Ollama host paths, Qdrant collection/filter-field mappings, output format and original UI filters. The workflow is exported with `active: false` for safe import.

## Key logic

- **Inventory image / text listing:** detect directly supported ingredients, retrieve candidates, rank to maximize available ingredients and minimize missing ones, then return one KB-grounded recipe and clearly listed missing ingredients. The second visual pass is a review, not unquestioned agreement with the first pass.
- **Text + ingredient image:** use the user's requested dish **and** verified available food. Do not substitute the requested dish with an unrelated dish just because ingredient overlap is higher.
- **Prepared-dish photo:** identify the prepared dish; do not claim that the dish's usual components are available in the home.
- **Written-recipe photo:** transcribe the original document as the authoritative source; any similar recipe in Qdrant is secondary.
- **Text-only:** keep the existing fine-tuned LoRA classifier and its trained schema unchanged.
- **Unrelated image or no usable query:** use existing refusal/error flow; never invent a recipe to satisfy the request.
- **Time, vegetarian, cuisine, calories, protein:** existing WebUI filters remain authoritative and are not adjusted by this revision.

## Import and test

1. Back up the current functioning workflow in n8n.
2. Import `recipe-helper-UNIVERSAL-AGENT-PROMPTS.json` as a **separate inactive** workflow.
3. Since it has the same webhook path, **deactivate the older active version before activating the new one**. If you need to keep the old workflow active for side-by-side tests, change the new workflow webhook path first.
4. Ensure Ollama models (`gemma3:4b`, `qwen2.5:3b`, `recipe-intent-lora:latest`, `bge-m3`) and Qdrant are reachable as in your original deployment.
5. Run the scenarios below using a variety of images and review n8n execution nodes, especially `Router`, `Vision ingredients`, `Vision verify inventory`, `Normalize 1`, `Sub_Search_Embed`, `Sub_Rank_Chef` and `Sub_Validate_Final_Build`.

| Input | Expected behavior |
|---|---|
| **Text only:** “I have spinach, rice and eggs.” | Intent ingredients; Qdrant match based on listed ingredients. |
| **Raw ingredients on a counter + text:** “What dinner can I make?” | Image inventory analysis; no assumptions about refrigeration; few missing ingredients. |
| **Open fridge + text:** “Vegetable soup” | Broad scan of image; recipe uses available vegetables when possible. |
| **Pantry shelf photo:** grain boxes, cans with legible labels | Confirm only clearly seen ingredients, don't guess contents of opaque jars. |
| **Finished dish photo:** pasta in sauce | Identify prepared dish, not a shopping inventory. |
| **Recipe website screenshot** | Preserve screenshot recipe content; don't replace its ingredients with the closest KB entry. |
| **Text + photo + 30-minute UI filter** | Keep `max_minutes=30`; select only candidates meeting the filter. |
| **Unrelated photo** | Reject or report no food, rather than generate a fake recipe. |

## Validation performed before export

- Workflow JSON parses correctly; 25 main nodes and 3 embedded tool subflows.
- Main node IDs and the connection topology match the prior workflow.
- JavaScript code and n8n JSON expression source compile syntactically under Node.js.
- Mock Qdrant ranking prefers a broccoli/carrot soup over a tomato-heavy recipe for a broccoli/carrot inventory, and correctly selects a salad or pasta for corresponding sample requests.
- Mock semantic-search preparation preserves a photographic inventory and UI filters, and handles text-only, prepared-dish photo and written-document modes.

**Not yet tested:** actual Ollama visual accuracy, Qdrant content-specific relevance, n8n import/version compatibility, execution times, model memory under simultaneous loads, or end-to-end live user requests. Model prompting alone cannot guarantee every visual ingredient will be identified correctly; more difficult images may need careful crops, a larger vision model, or manual user correction.

## Known scope limits

- Image + text uses the text primarily as a *dish preference*. Explicit extra groceries listed in free-text with a photo are not separately run through the LoRA classifier as a second inventory source; UI filters are supported. This revision avoids intrusive changes to the wiring and does not claim this capability.
- Confidence estimates are self-reported by the model, not calibrated probabilities. Avoid turning uncertain identifications into authoritative inventory facts.
- The deterministic Qdrant filter fields depend on the actual stored payload schema. They have **not** been modified.
- For dietary allergies, do not assume the current vegetarian/time filter alone establishes an allergy-safe dish.

## Rollback

If any end-to-end test fails, deactivate this workflow and reactivate your backed-up previous workflow. The new JSON does not delete or change your existing Ollama models or LoRA adapter.
