# Recipe Helper

A multimodal, multi-agent recipe assistant on Telegram. Send a **photo of ingredients, a photo of a dish, a screenshot of a recipe, or text**, and get a matching recipe back.

Everything runs **locally and for free**: n8n (automation), Ollama (`gemma3:4b`, `qwen2.5:3b`, `bge-m3`) and Qdrant (vector store). No cloud API.

---

## What it does

| Input | Output |
|---|---|
| **Ingredients** (photo or text) | Recipe with the fewest missing ingredients: "You have" / "Missing", up to 3 substitutions, steps, 2 close alternatives |
| **Dish** (photo or name) | Recipe with ingredients and steps |
| **Recipe screenshot** | Recipe extracted from the image (no database search) |
| **Text in French or Arabic** | Translated to English before searching |

Optional filters (in text or photo caption): `vegetarian`, and a time limit like `under 30 minutes`.
Salt, pepper, water, oil and sugar are pantry basics and never count as missing.

---

## How it works

![architecture](report/architecture.png)

1. **Telegram Trigger** receives the message and immediately sends a progress message.
2. **Input Type** switch: photo or text.
3. **Text path:** *Text intent* agent (`qwen2.5:3b`) detects ingredients vs dish, time limit, vegetarian flag, and translates to English.
4. **Image path:** the **Router** agent (`gemma3:4b`, vision) classifies the photo as `ingredients_photo`, `dish_photo` or `recipe_document`, then *Vision ingredients*, *Vision dish* or *Recipe parser* reads it.
5. **Normalize** turns every input into `{mode, query, user_ingredients, filters}`.
6. Recipe screenshots skip retrieval. Everything else is embedded with `bge-m3` and searched in Qdrant (`recipes_rich`).
7. **Rank recipes** (code): top 40 candidates for ingredient inputs (fewest missing wins), top 5 for dish/text inputs.
8. **Chef** agent (`gemma3:4b`) returns an intro, up to 3 substitutions and a tip. **Validator** (`qwen2.5:3b`) checks the substitutions (fail-open). **Final answer** (code) builds the message, max 4000 characters.

Design rule: the small models only read images, understand text and suggest substitutes. Everything countable or checkable is done in code.

**Knowledge base:** Food.com `RAW_recipes.csv`, first 6,000 rows indexed (5,845 kept after dropping recipes with fewer than 3 ingredients or 2 steps). One chunk per recipe, embedded with `bge-m3` (1024 dims), Qdrant with cosine distance and payload indexes on `minutes` and `tags`.

---

## Requirements

- **OS:** Linux (developed on Ubuntu 24.04). macOS/Windows with Docker Desktop untested.
- **RAM / disk:** 16 GB RAM recommended, about 10 GB free disk (models ~6.5 GB) plus ~900 MB for the dataset.
- **GPU:** optional. Without one, each photo takes several minutes.
- **Software:** Docker Engine + Compose plugin, Ollama, Python 3.10+, Node.js 18+ (unit tests only), `cloudflared` (Telegram webhook only).
- **Accounts:** Telegram (bot from @BotFather) and Kaggle (dataset download).

Tested with n8n 2.42.4 (self-hosted, Docker).

---

## Repository layout

```
recipe-helper/
├── docker-compose.yml                    n8n + Qdrant
├── data/                                 RAW_recipes.csv goes here (not committed)
├── workflows/
│   └── recipe-helper-telegram-v2.json    CURRENT workflow (use this one)
├── scripts/
│   ├── index_rich.py                     builds recipes_rich (used by the workflow)
│   ├── eval.py                           retrieval evaluation (hit@k, MRR)
│   ├── eval_ingredients.py               ingredient-matching evaluation
│   └── ranker.py                         Python copy of the ranking node
├── prompts/prompt_library.md             versioned prompts, failures, fixes
├── eval/                                 queries and results
├── report/                               technical report and architecture diagram
└── tests/test_js.js                      unit tests of the n8n code nodes
```

Other files in `workflows/` and `scripts/` (`recipe-helper-telegram.json`, `recipe-helper-full.json`, `recipe-helper.json`, `index.py`, `e2e_test.py`, `build_full_workflow.py`) are older versions kept for reference only.

---

## Setup

### 1. Docker

Install Docker Engine + Compose plugin (https://docs.docker.com/engine/install/ubuntu/), then:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

If Docker complains about `docker-credential-desktop`, reset the leftover config: `echo '{}' > ~/.docker/config.json`.

### 2. Ollama and models

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ollama pull qwen2.5:3b
ollama pull bge-m3
```

Make Ollama reachable from the n8n container (it listens on localhost by default):

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

If ufw is active: `sudo ufw allow from 172.16.0.0/12 to any port 11434 proto tcp`

### 3. Code and dataset

```bash
git clone <your-repo-url> recipe-helper && cd recipe-helper
mkdir -p data
```

Download **Food.com Recipes and Interactions** from Kaggle (https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions) and extract only `RAW_recipes.csv` (not `PP_recipes.csv`):

```bash
unzip ~/Downloads/archive.zip RAW_recipes.csv -d data/
```

### 4. Start n8n and Qdrant

`docker-compose.yml` (if you don't have one):

```yaml
services:
  n8n:
    image: n8nio/n8n
    restart: unless-stopped
    ports: ["5678:5678"]
    environment:
      - N8N_SECURE_COOKIE=false
      - WEBHOOK_URL=${WEBHOOK_URL:-http://localhost:5678}
    extra_hosts:
      - "host.docker.internal:host-gateway"   # lets n8n reach Ollama on Linux
    volumes: ["n8n_data:/home/node/.n8n"]
  qdrant:
    image: qdrant/qdrant
    restart: unless-stopped
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]
volumes:
  n8n_data:
  qdrant_data:
```

```bash
docker compose up -d
curl -s http://localhost:6333/collections
docker compose exec n8n wget -qO- http://host.docker.internal:11434/api/tags   # should list your 3 models
```

Open http://localhost:5678 and create the owner account (first start only).

### 5. Index the recipes

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pandas qdrant-client ollama
python scripts/index_rich.py          # ~10-20 min on CPU; use "index_rich.py 8000" for another size
```

It ends with `recipes_rich done <count>`.

### 6. Telegram bot

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the token.
2. In n8n: **Credentials → Create credential → Telegram API**, paste the token. The token lives only in n8n, never in the repo.

### 7. Public URL for the webhook

Telegram needs an HTTPS address. Use a Cloudflare quick tunnel:

```bash
# install once
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# every session (terminal 1, keep open)
cloudflared tunnel --url http://localhost:5678
```

Copy the printed `https://xxxx.trycloudflare.com` address and restart n8n with it (terminal 2):

```bash
WEBHOOK_URL=https://xxxx.trycloudflare.com docker compose up -d
docker compose exec n8n printenv WEBHOOK_URL      # must print the same address
```

The address **changes every time the tunnel restarts**, so repeat this each session.

---

## Run it

### Import the workflow (once)

1. Open http://localhost:5678 (not the tunnel address).
2. **Workflows → ⋯ → Import from file →** `workflows/recipe-helper-telegram-v2.json`.
3. Select your **Telegram account** credential in the *Telegram Trigger* and each *Send a text message* node.
4. Save. The Ollama and Qdrant calls are plain HTTP nodes (`http://host.docker.internal:11434`, `http://qdrant:6333`) and need no credential.

### Publish and use

1. Click **Publish**. A bot can have only one trigger, so unpublish any other workflow using the same bot.
2. Send a message or a photo to your bot. You get an "Analyzing" message first, then the answer after one to a few minutes.
3. Every run is visible in the **Executions** tab.

Notes:
- While published, **Execute workflow** is unavailable. To debug, Unpublish, run, then Publish again.
- Send photos as normal photos, not files. Images under 1 MB are faster.

### Restart checklist (after a reboot)

```bash
sudo systemctl start docker ollama
cloudflared tunnel --url http://localhost:5678                       # terminal 1, copy the address
WEBHOOK_URL=https://xxxx.trycloudflare.com docker compose up -d      # terminal 2
```

Then in n8n: Unpublish and Publish the workflow again (re-registers the Telegram webhook) and send one message to warm up the models.

---

## Evaluation and tests

```bash
source .venv/bin/activate
python scripts/eval.py | tee eval/results.txt                          # retrieval: 10 queries, hit@k and MRR
python scripts/eval_ingredients.py | tee eval/results_ingredients.txt  # ingredient matching, simulated users
cd tests && node test_js.js                                            # 27 unit tests of the code nodes
```

Note: the evaluation sets are small (10 queries, simulated users), so scores are directional only.

---

## Configuration

| What | Where |
|---|---|
| Models | `model` field in each HTTP Request node (Router, Vision x2, Recipe parser, Chef: `gemma3:4b`; Text intent, Validator: `qwen2.5:3b`) |
| Number of candidates | node *RAG search*: `limit` 40 for ingredient inputs, 5 otherwise |
| Ingredient confidence threshold | node *Normalize 1*: `c >= 0.6` |
| Pantry basics | node *Rank recipes*: `STAPLES` list (keep `scripts/ranker.py` in sync) |
| Ranking rules | node *Rank recipes* |
| Corpus size | `python scripts/index_rich.py N` |
| Search collection | URL of node *RAG search* (`recipes_rich`) |
| Message length limit | node *Final answer* (3900 chars for steps, 4000 total) |

The files in `tests/js/` are copies of the code nodes (the workflow JSON is the source of truth). After editing a node in n8n, update the copy and re-run the tests.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` from a Python script | Qdrant is not running: `docker compose up -d` |
| n8n cannot reach Ollama (timeout) | Apply the Ollama host and ufw steps in Setup 2, then re-test with the `wget` command in Setup 4 |
| HTTP node: "Method not allowed" | Node is set to GET. All model and Qdrant calls must be **POST**. Re-import the workflow |
| HTTP node: "JSON Body is not valid JSON" | Code pasted in the wrong field. Re-import the workflow |
| Bot never answers | Check in order: `cloudflared` still running; `printenv WEBHOOK_URL` matches the tunnel address; workflow published (Unpublish then Publish); Executions tab shows whether a run started |
| "can't listen for test executions at the same time as production ones" | Workflow is published. Unpublish before using Execute workflow |
| Telegram 400 "can't parse entities" | Markdown characters in the message. The code nodes strip them; keep that step if you edit them |
| "Analyzing..." arrives after the answer | Keep the progress message node above the Input Type branch |
| `model not found` | Run the three `ollama pull` commands again |
| Very slow answers | Normal on CPU. Use smaller photos, keep models loaded (`ollama run gemma3:4b "hi" --keepalive 30m`), or use a GPU |
| No result or odd recipe | Corpus has only 5,845 recipes. Try other ingredients, drop the time limit, or index more (`index_rich.py 12000`) |

---

## Known limits

- Vision model (`gemma3:4b`) can misread ingredients or quantities on dark, blurry or crowded photos. Low-confidence items are flagged "not sure about".
- Corpus is English only. Non-English text is translated, but photos of non-English recipe pages stay in their original language.
- The 3B validator is unreliable on counts and lists, so it only judges substitutions.
- The bot only works while the laptop, Docker, Ollama and the tunnel are running.
- No nutrition data, no allergen checks.

---

## Security and data

- The Telegram token and n8n password are never stored in the repo. Credentials live in n8n only.
- `.gitignore` excludes `.venv/`, `data/RAW_recipes.csv` and `.env`.
- Dataset: Food.com Recipes and Interactions (Majumder, Li, Ni, McAuley, EMNLP 2019). Not redistributed; used for coursework only.
- Photos are processed locally by Ollama and never sent to a cloud service. Telegram itself stores the messages, as with any bot.