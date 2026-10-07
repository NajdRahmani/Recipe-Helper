# Claude handoff: Recipe Helper

## Project

Workspace: `recipe-helper`

The project is a multimodal recipe assistant built with n8n, Ollama, and Qdrant. It accepts typed requests, ingredient photos, cooked-dish photos, and recipe screenshots.

## Completed infrastructure

- Docker Compose services are running:
  - n8n on `http://localhost:5678`
  - Qdrant on `http://localhost:6333`
- Ollama is reachable from the n8n container through `host.docker.internal`.
- Installed models:
  - `gemma3:4b` for vision and Chef responses
  - `qwen2.5:3b` for validation
  - `bge-m3` for embeddings
- Qdrant collections exist:
  - `recipes_fixed`
  - `recipes_struct`

## Retrieval work

`scripts/index.py` indexes the first 2,000 non-null Food.com recipes from `data/RAW_recipes.csv`.

The selected collection is `recipes_fixed`, using top-5 retrieval:

- hit@5: `0.90`
- MRR: `0.75`

The structured-chunk alternative scored hit@5 `0.90` and MRR `0.68`.

The benchmark is in `eval/results.txt`; queries are in `eval/queries.csv`.

## n8n workflow

The complete workflow was generated and imported into n8n as:

- Name: `recipe-helper-full`
- Workflow ID: `859164a4-5c6f-429d-8147-17eeee31fdc4`
- Node count: 24
- Connection groups: 21

The canonical export is [workflows/recipe-helper.json](workflows/recipe-helper.json).

The workflow architecture contains:

1. Recipe Helper Form Trigger
2. Input Type switch
3. Image to base64
4. Router
5. Parse router
6. Route by type
7. Vision ingredients
8. Vision dish
9. Recipe parser
10. Normalize 1, Normalize 2, Normalize 3
11. Normalize text
12. Has query
13. Embed query
14. RAG search against `recipes_fixed`
15. Has results
16. Build context
17. Chef
18. Validator
19. Final answer
20. Nothing found, No match, and Your recipe form endings

The generator is [scripts/build_full_workflow.py](scripts/build_full_workflow.py). It creates [workflows/recipe-helper-full.json](workflows/recipe-helper-full.json), validates connection targets, and was used for the successful n8n import.

## Direct pipeline validation

An independent text-path test for `chicken pasta` succeeded:

1. `bge-m3` created the query embedding.
2. Qdrant returned five recipe candidates.
3. `gemma3:4b` generated a recipe answer.
4. `qwen2.5:3b` returned JSON with `valid: true` and no issues.

This confirms the services work together, but it is not a replacement for an n8n form execution.

## Documentation completed

- [README.md](README.md)
- [report/report.md](report/report.md)
- [report/architecture.png](report/architecture.png)
- [report/architecture.svg](report/architecture.svg)
- [report/architecture.dot](report/architecture.dot)
- [prompts/prompt_library.md](prompts/prompt_library.md)
- [eval/e2e_tests.md](eval/e2e_tests.md)
- [report/failed_attempts.md](report/failed_attempts.md)

Python syntax checks and the retrieval benchmark pass.

## Remaining verification and cleanup

The workflow has been imported and structurally validated. HTTP nodes are POST with timeout `300000` and three retries, and the Form Trigger is configured for a response node with optional image/message fields. Remaining work:

1. Add 10 ingredient photos, 3 dish photos, and 3 recipe screenshots under `eval/images/`.
2. Run `python scripts/e2e_test.py` again for the full multimodal set.
3. Record observed image results in `eval/e2e_tests.md`.
4. Capture screenshots for any failures and update v1/v2 prompt notes only when failures are observed.
5. Run the n8n Form Test URL once for the final UI-level smoke test.

Do not use or reproduce credentials from the conversation. The password was exposed during setup and should be rotated.