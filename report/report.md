# Recipe Helper Report

## Use case and architecture

Recipe Helper accepts a typed request or an image. Images are classified into raw ingredients, a cooked dish, or a written recipe document. The selected vision agent produces a normalized query, which is embedded with `bge-m3` and matched against the Food.com recipe collection in Qdrant. A Chef agent writes the answer from the retrieved context, and a separate Validator checks grounding and ingredient claims before the form completion.

The architecture is shown in `architecture.png` and described by `architecture.dot`. The n8n export contains the same Router, vision, normalization, RAG, Chef, Validator, and completion path.

## Prompt engineering

The prompts use role instructions, constrained JSON output, explicit uncertainty fields, and grounding rules. The Router separates the three image tasks. The ingredient agent is told to list only clearly visible items. The recipe parser is told to copy only written quantities and steps. The Chef receives only the user request and retrieved candidates. The Validator uses a different model and checks HAVE ingredients, non-empty steps, and context grounding.

The prompt library is in `prompts/prompt_library.md`. The terminal v1 E2E run passed 3/3 text cases. There were no observed failures to drive three evidence-based v2 changes, and image/document cases remain pending because `eval/images/` is empty. No unobserved results are claimed.

## RAG evaluation

The corpus is the first 2,000 rows of Food.com `RAW_recipes.csv`. `scripts/index.py` compares fixed-size overlapping chunks with structured ingredient/step chunks. Both collections use 1,024-dimensional `bge-m3` embeddings and Qdrant cosine distance.

| Collection | k | Hit@k | MRR |
|---|---:|---:|---:|
| recipes_fixed | 3 | 0.90 | 0.75 |
| recipes_fixed | 5 | 0.90 | 0.75 |
| recipes_fixed | 10 | 1.00 | 0.76 |
| recipes_struct | 3 | 0.90 | 0.68 |
| recipes_struct | 5 | 0.90 | 0.68 |
| recipes_struct | 10 | 1.00 | 0.70 |

The selected configuration is `recipes_fixed`, top-5. The test set has only ten queries, so the difference should be treated as directional rather than definitive.

An independent live text-path check for `chicken pasta` retrieved five candidates, generated a Chef answer with `gemma3:4b`, and returned `valid: true` with no issues from `qwen2.5:3b`. This confirms the Ollama and Qdrant services work together outside the n8n form; it is not counted as an n8n end-to-end score.

The n8n Form Trigger smoke test for `chicken pasta` also completed with execution status `success` after the HTTP Request node version fix.

## Multi-agent design

| Agent | Role | Model | Input | Output |
|---|---|---|---|---|
| Router | classify image type | gemma3:4b | image | type and confidence |
| Vision ingredients | identify visible foods | gemma3:4b | image | ingredients and uncertainty |
| Vision dish | identify plated dish | gemma3:4b | image | dish and likely ingredients |
| Recipe parser | extract written recipe | gemma3:4b | image | title, ingredients, steps |
| Chef | compose grounded answer | gemma3:4b | query and candidates | recipe answer |
| Validator | verify claims | qwen2.5:3b | input, context, answer | valid flag and issues |

Separate agents make the image task explicit and let validation operate as an independent check. A single call would mix classification, extraction, retrieval, and answer generation. A hierarchical agent would add orchestration complexity without a demonstrated benefit for this small fixed pipeline.

## Multimodality

`gemma3:4b` supports image input through Ollama's `/api/chat` endpoint. The workflow converts uploaded binary data to base64, routes the image, and uses the same model for the selected vision task. Small images are recommended because inference is CPU-bound. The planned test set contains ten ingredient photos, three dish photos, and three recipe screenshots.

## Failed attempts and limits

See `failed_attempts.md`. The main retrieval limitation is vague requests where the recipe name contributes little semantic signal; structured chunks can also fill top-k with duplicate recipe entries. The validator model intentionally differs from the Chef model and can still miss subtle errors. The 10-query retrieval set is small. CPU vision inference can take several minutes per image, and the planned 17-case multimodal set remains pending because `eval/images/` is empty; the terminal text subset currently passes 3/3.