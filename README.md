# Recipe Helper (n8n + Ollama + Qdrant)

Recipe assistant for text, ingredient photos, cooked-dish photos, and recipe screenshots.

## Prerequisites

- Docker and Docker Compose
- Ollama with `gemma3:4b`, `qwen2.5:3b`, and `bge-m3`
- Python 3.10+
- Food.com `RAW_recipes.csv` in `data/`

## Run the local retrieval stack

```bash
ollama pull gemma3:4b
ollama pull qwen2.5:3b
ollama pull bge-m3
sudo systemctl edit ollama
# Add under [Service]: Environment="OLLAMA_HOST=0.0.0.0"
# Then save, close, and restart:
sudo systemctl restart ollama
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate
pip install pandas qdrant-client ollama
python scripts/index.py
python scripts/eval.py
python scripts/e2e_test.py
```

The indexer builds `recipes_fixed` and `recipes_struct` from the first 2,000 recipes. The current evaluation selects `recipes_fixed` with top-5 retrieval: hit@5 is 0.90 and MRR is 0.75 on the 10-query set.

## n8n

Open `http://localhost:5678`, import `workflows/recipe-helper.json`, and set the Ollama HTTP credential to `http://host.docker.internal:11434` if n8n asks for one. Open the imported `recipe-helper-full` workflow, execute it, and open its Form Trigger Test URL. The n8n workflow uses `gemma3:4b` for vision and Chef responses, `qwen2.5:3b` for validation, `bge-m3` for embeddings, and Qdrant for retrieval.

## Evaluation

The retrieval benchmark is in `eval/results.txt`. Terminal E2E runs use `scripts/e2e_test.py` and save JSON artifacts under `eval/runs/`. Add 10 ingredient photos, 3 dish photos, and 3 recipe screenshots under `eval/images/` before running the multimodal cases. Manual n8n form runs belong in `eval/e2e_tests.md` and must be recorded from actual submissions.