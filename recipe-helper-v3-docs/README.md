# Recipe Helper

A multimodal, multi-agent recipe assistant on Telegram. Send it **a photo of your ingredients, a photo of a dish, a screenshot of a recipe, or text**, and it answers with a recipe that fits the input.

Final project of *Advanced Deep Learning* (Esprit, 5DS, 2026-2027): AI automation with prompt engineering, RAG, multi-agent design and multimodality.
Author: Najd Rahmani.

Everything runs **locally and for free**: n8n (automation), Ollama (`gemma3:4b`, `qwen2.5:3b`, `bge-m3`) and Qdrant (vector store), all on one machine. No cloud API, no fine-tuning.

---

## Contents

1. [What it does](#1-what-it-does)
2. [How it works](#2-how-it-works)
3. [Requirements](#3-requirements)
4. [Repository layout](#4-repository-layout)
5. [Setup, step by step](#5-setup-step-by-step)
6. [Run it](#6-run-it)
7. [Evaluation and tests](#7-evaluation-and-tests)
8. [Configuration](#8-configuration)
9. [Troubleshooting](#9-troubleshooting)
10. [Known limits](#10-known-limits)
11. [Where each course requirement lives](#11-where-each-course-requirement-lives)
12. [Security and data](#12-security-and-data)

---

## 1. What it does

The answer depends on what the user sends.

| Input | What the user gets |
|---|---|
| **Ingredients** (photo, or text such as `I have eggs, tomatoes and cheese`) | The recipe that needs the **fewest extra ingredients**, with "You have" and "Missing", up to 3 substitutions, the steps, and 2 other close options |
| **Dish** (photo, or a dish name such as `lasagna`) | The recipe with "Ingredients needed" and steps. No have/missing, because the user has not said what they own. For a photo it shows the detected dish and its alternatives. When nothing close exists it says "No exact recipe found, this is the closest one" |
| **Recipe screenshot** (photo of a page, card or screen) | The user's **own recipe** as extracted (ingredient lines with quantities, steps), then a similar recipe from the knowledge base as a labelled reference ("close", "partial" or "loose match"). No have/missing wording. If the image has no readable steps, steps are suggested from the reference recipe and labelled as such; a warning appears when parts were hard to read |
| **Greeting, `/start`, no food content** | A help message |
| **An image that is not food** | A polite message asking for ingredients, a dish or a recipe |
| **Text in French, Arabic or Tunisian dialect written in Latin letters** | Understood and translated to English before searching |

Extra options (in the text, or in the caption of a photo): `vegetarian`, and a time limit such as `under 30 minutes` or `30 min`.

Message format (illustrative example for an ingredients photo):

```
Simple chicken rice (30 min)
A simple one-pot dish of chicken, rice and onion.

Detected in your photo: chicken, rice, onion, garlic

You have (4 of 4): chicken, rice, onion, garlic
You have everything you need!
Pantry basics: salt, water, olive oil

Steps:
1. ...

Other close options: Chicken rice bake (missing 2); Chicken tikka (missing 5)

Tip: ...
```

Salt, pepper, water, oil and sugar are treated as pantry basics and never counted as missing.

---

## 2. How it works

![architecture](report/architecture.png)

1. **Telegram Trigger** receives the message and a progress message is sent right away (analysis can take minutes on CPU).
2. **Input Type** switch: photo or text.
3. **Text path:** the *Text intent* agent (`qwen2.5:3b`) decides whether the user listed ingredients, named a dish, or just greeted the bot, extracts a time limit and the vegetarian flag, and translates to English.
4. **Image path:** the photo is downloaded, converted to base64, and the **Router** agent (`gemma3:4b`, vision) describes what is visible and classifies the image as `ingredients_photo`, `dish_photo`, `recipe_document` or `not_food` (a doubtful `not_food` below 0.6 confidence falls back to ingredients). One vision agent then reads the image: *Vision ingredients*, *Vision dish* or *Recipe parser*.
5. A **Normalize** node turns every input into one contract: `{mode, query, title_query, user_ingredients, filters}`. Help messages and empty inputs stop here with a reply.
6. The query is embedded with `bge-m3` and searched in Qdrant (`recipes_rich`): 40 candidates for ingredient inputs, 10 otherwise, with optional filters on cooking time and the vegetarian tag. Recipe screenshots are searched too, to find a similar reference recipe.
7. **Rank recipes** (code): for ingredient inputs it keeps the recipe with the fewest missing ingredients; for dish and text inputs it prefers names that contain the query words; for screenshots it scores name match plus ingredient overlap. It also writes the context block that the Chef receives.
8. **Chef** agent (`gemma3:4b`): returns JSON with an intro sentence, up to 3 substitutions and one tip. **Parse chef** (code) removes invalid substitutions.
9. **Validator** agent (`qwen2.5:3b`): says whether each substitution is sensible and whether the intro and tip are consistent with the recipe.
10. **Final answer** (code) builds the Telegram message: substitutions are dropped when the validator rejects them or when its verdict cannot be read, meat is removed from substitutions when vegetarian was requested, and the text is kept under 4000 characters.

Design rule learned from the failures (see `prompts/prompt_library.md`): the small models only read images, understand free text and write short text. Everything countable or checkable (which recipe, have/missing sets, steps, formatting, length) is done by code.

### Agents

| Agent | Model | Input | Output |
|---|---|---|---|
| Router | gemma3:4b (vision) | image | visible description, type (4 classes), confidence |
| Vision ingredients | gemma3:4b | image | ingredients with confidence, uncertain list |
| Vision dish | gemma3:4b | image | dish, confidence, main ingredients, alternatives |
| Recipe parser | gemma3:4b | image | recipe in its original language, English title and ingredient names, completeness flag |
| Text intent | qwen2.5:3b | message | ingredients, dish or help; time limit; vegetarian; English |
| Chef | gemma3:4b | context built by code | intro, substitutions, tip |
| Validator | qwen2.5:3b | context and Chef output | verdict per substitution, intro ok, tip ok |

Retrieval and ranking are tools (Qdrant search plus a code node), not agents.

### Knowledge base

- Corpus: Food.com recipes (`RAW_recipes.csv`, more than 180,000 recipes). The first 60,000 rows are indexed (`python scripts/index_rich.py 60000`); recipes with fewer than 3 ingredients or 2 steps are skipped ([FILL: count printed by `recipes_rich done` ] indexed in our run).
- Three chunking strategies are compared: `recipes_fixed` (800-character windows, 100 overlap), `recipes_struct` (an ingredients chunk and a steps chunk per recipe) and `recipes_rich` (one chunk per recipe, `name. Ingredients: ...` embedded, full recipe in the payload). The workflow uses `recipes_rich`.
- Embeddings: `bge-m3` (1024 dimensions). Store: Qdrant, cosine distance, payload indexes on `minutes` and `tags`.

---

## 3. Requirements

| Item | Needed |
|---|---|
| OS | Linux (developed on Ubuntu 24.04). macOS and Windows should work with Docker Desktop but were not tested |
| RAM | 16 GB recommended. The models need about 6.5 GB on disk (`gemma3:4b` 3.3 GB, `qwen2.5:3b` 1.9 GB, `bge-m3` 1.2 GB). The workflow keeps the chat models loaded for 15 minutes after each call (`keep_alive`), so about 7 GB of RAM stays in use during a session |
| GPU | Optional. Without a GPU, each request takes one to several minutes |
| Disk | About 10 GB free, plus about 900 MB for the Kaggle download |
| Software | Docker Engine with the Compose plugin, Ollama, Python 3.10+, `cloudflared` (only for Telegram) |
| Accounts | A Telegram account (bot from @BotFather) and a free Kaggle account (to download the dataset) |

Tested with n8n 2.42.4 (self-hosted, Docker).

---

## 4. Repository layout

```
recipe-helper/
├── README.md
├── docker-compose.yml          n8n + Qdrant
├── start.sh / stop.sh          one-command start and stop (section 6.0)
├── .gitignore                  .venv/, data/RAW_recipes.csv, .env, .tunnel.pid, .tunnel.log
├── data/                       RAW_recipes.csv goes here (not committed)
├── workflows/
│   ├── recipe-helper-telegram-v3.json   CURRENT workflow (use this one)
│   ├── recipe-helper-telegram-v2.json   previous version (kept for the before/after)
│   ├── recipe-helper-telegram.json      first Telegram version
│   ├── recipe-helper-full.json          early Form-trigger version (first prompts, no Telegram)
│   └── recipe-helper.json               canonical export of the Form version
├── scripts/
│   ├── index.py                 builds recipes_fixed and recipes_struct (chunking comparison)
│   ├── index_rich.py            builds recipes_rich (used by the workflow)
│   ├── eval.py                  retrieval evaluation, 10 queries, hit@k and MRR
│   ├── eval_ingredients.py      simulated "user has these ingredients" evaluation
│   ├── eval_rerank.py           dish-name retrieval with the same name rerank as the workflow
│   ├── ranker.py                Python copy of the ingredient ranking, used by eval_ingredients.py
│   ├── e2e_test.py              terminal harness of the first pipeline (plumbing check only)
│   └── build_full_workflow.py   generator of the early Form workflow
├── prompts/prompt_library.md    versioned prompts, failures, fixes
├── eval/
│   ├── queries.csv              10 retrieval test queries
│   ├── results.txt              retrieval scores
│   ├── results_ingredients.txt  ingredient-matching scores
│   ├── e2e_tests.md             test tables (harness, live failures, v3 test plan, validator metric)
│   ├── images/                  test photos (optional)
│   └── runs/                    JSON outputs of the terminal harness
├── report/
│   ├── report.md                technical report
│   └── architecture.png/.svg/.dot
└── tests/                       unit tests written for the v2 code nodes (outdated for v3, kept for history)
```

`scripts/ranker.py` copies the ingredient-ranking rules of the *Rank recipes* node. If you change the staples or the matching rules in one place, change the other.

---

## 5. Setup, step by step

### 5.1 Install Docker

Follow https://docs.docker.com/engine/install/ubuntu/ (Docker Engine + Compose plugin), then:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world
```

If Docker complains about `docker-credential-desktop`, a leftover Docker Desktop config is the cause:
```bash
cp ~/.docker/config.json ~/.docker/config.json.bak && echo '{}' > ~/.docker/config.json
```

### 5.2 Install Ollama and the models

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ollama pull qwen2.5:3b
ollama pull bge-m3
```

Make Ollama reachable from the n8n container (it listens on localhost only by default):

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama
ss -tlnp | grep 11434        # must show *:11434 or 0.0.0.0:11434
```

If a firewall (ufw) is active, allow Docker's networks to reach Ollama:
```bash
sudo ufw allow from 172.16.0.0/12 to any port 11434 proto tcp
```

### 5.3 Get the code and the dataset

```bash
git clone <your-repo-url> recipe-helper
cd recipe-helper
mkdir -p data
```

Download **Food.com Recipes and Interactions** from Kaggle (https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions), then extract only the file we use:

```bash
unzip ~/Downloads/archive.zip RAW_recipes.csv -d data/
head -c 300 data/RAW_recipes.csv      # header: name,id,minutes,contributor_id,submitted,tags,nutrition,n_steps,steps,description,ingredients,n_ingredients
```

Use `RAW_recipes.csv`, not `PP_recipes.csv` (the latter is tokenised numbers).

### 5.4 Start n8n and Qdrant

`docker-compose.yml` (use this if you do not have one yet):

```yaml
services:
  n8n:
    image: n8nio/n8n
    restart: unless-stopped
    ports: ["5678:5678"]
    environment:
      - N8N_SECURE_COOKIE=false          # local http only
      - WEBHOOK_URL=${WEBHOOK_URL:-http://localhost:5678}
    extra_hosts:
      - "host.docker.internal:host-gateway"   # lets n8n reach Ollama on the host (needed on Linux)
    volumes: ["n8n_data:/home/node/.n8n"]
  qdrant:
    image: qdrant/qdrant
    restart: unless-stopped
    ports: ["127.0.0.1:6333:6333"]       # local only
    volumes: ["qdrant_data:/qdrant/storage"]
volumes:
  n8n_data:
  qdrant_data:
```

```bash
docker compose up -d
docker compose ps                                   # both services running
curl -s http://localhost:6333/collections           # Qdrant answers
docker compose exec n8n wget -qO- http://host.docker.internal:11434/api/tags   # lists your 3 models
```

Open http://localhost:5678 and create the owner account (first start only).

### 5.5 Python environment and indexing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas qdrant-client ollama
python scripts/index_rich.py 60000      # the project used 60,000 rows; the time grows with the number of rows
```

It prints its progress and ends with `recipes_rich done <count>`: that count is the number of recipes in the knowledge base. The default without an argument is 6,000 rows, which is enough for a quick test. A smaller number gives a faster but less varied knowledge base.

Optional, to reproduce the chunking comparison (adds `recipes_fixed` and `recipes_struct`, first 2,000 recipes, and a `recipes_rich_2k` collection with the same 2,000 recipes so that the three strategies are compared on the same corpus):
```bash
python scripts/index.py
python scripts/index_rich.py 2000 recipes_rich_2k
```

### 5.5b Telegram bot

1. In Telegram, open **@BotFather**, send `/newbot`, choose a name and a username ending in `bot`, and copy the token.
2. In n8n: **Credentials → Create credential → Telegram API**, paste the token, save. The token lives only in n8n, never in the repository.
3. Optional: to let `start.sh` verify the webhook, create a file `.env` next to it containing `TELEGRAM_BOT_TOKEN=<token>` (the file is git-ignored).

### 5.6 Public URL for the Telegram webhook

Telegram needs an HTTPS address that reaches your n8n. On a laptop, use a Cloudflare quick tunnel (`start.sh` does the following for you).

```bash
# install once
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb

# every session (terminal 1, leave it open)
cloudflared tunnel --url http://localhost:5678
```

Copy the printed `https://xxxx.trycloudflare.com` address, then restart n8n with it (terminal 2):

```bash
WEBHOOK_URL=https://xxxx.trycloudflare.com docker compose up -d
docker compose exec n8n printenv WEBHOOK_URL      # must print the same address
```

The address **changes every time the tunnel restarts**, so repeat this step (and the re-publish in 6.2) each session.

---

## 6. Run it

### 6.0 One-command start

```bash
chmod +x start.sh stop.sh      # first time only
./start.sh                     # Docker, Ollama, tunnel, n8n, Qdrant, health checks, model warm-up
./stop.sh                      # stops the tunnel, n8n and Qdrant (data is kept)
```

`./start.sh --no-warmup` skips the model warm-up. The script prints the tunnel address, checks that the `recipes_rich` collection and the three models exist, and (when a `.env` token is present) checks that the Telegram webhook points to the new tunnel.

### 6.1 Import the workflow (once)

1. Open http://localhost:5678 (not the tunnel address).
2. **Workflows → ⋯ next to "Create workflow" → Import from file →** `workflows/recipe-helper-telegram-v3.json`.
3. Open the *Telegram Trigger* and each Telegram node (the progress message and the replies) and select your **Telegram account** credential.
4. The Ollama and Qdrant calls are plain HTTP nodes (`http://host.docker.internal:11434`, `http://qdrant:6333`), so they need no credential.
5. Click **Save**.

### 6.2 Publish and use

1. Make sure no other workflow uses the same Telegram bot (a bot can have only one trigger): unpublish any older Telegram version.
2. Click **Publish** on `recipe-helper-telegram-v3`.
3. Open your bot in Telegram and send a message or a photo. You get an "Analyzing your request" message first, then the answer after one to a few minutes.
4. Every run is visible in the **Executions** tab, node by node.

Notes:
- While the workflow is published you cannot use **Execute workflow** (Telegram allows one listener). To debug, **Unpublish**, run, then publish again.
- Send photos as normal photos, not as files.
- Small images (under 1 MB) are faster.

### 6.3 Restart checklist (after a reboot)

Run `./start.sh`. If the bot stays silent, in n8n **Unpublish** and **Publish** the workflow again (this re-registers the Telegram webhook) and send one message to warm up the models.

### 6.4 Older Form-trigger workflow

`workflows/recipe-helper-full.json` is the first version, triggered by a web form instead of Telegram, using the first prompts and the `recipes_fixed` collection (build it with `python scripts/index.py`). It is kept as a reference and as a fallback without a public URL. Use the v3 Telegram workflow for the behaviour described here.

---

## 7. Evaluation and tests

```bash
source .venv/bin/activate

# 1) retrieval quality: 10 queries, hit@k and MRR for the three chunking strategies
python scripts/eval.py | tee eval/results.txt

# 2) ingredient matching: vector top-1 vs top-40 + rerank, simulated users, source recipe excluded
python scripts/eval_ingredients.py | tee eval/results_ingredients.txt

# 3) dish-name retrieval as the workflow does it (vector + name rerank), with the misses listed
python scripts/eval_rerank.py | tee eval/results_rerank.txt
```

| What | Where | Note |
|---|---|---|
| Retrieval scores and chunking comparison | `eval/results.txt`, `report/report.md` section 3 | 10 queries is a small set, differences of one query are directional |
| Ingredient matching scores | `eval/results_ingredients.txt` | simulated users spell ingredients like the corpus, so this is an upper bound |
| Live Telegram failures, the v3 test plan, the validator drop-rate metric | `eval/e2e_tests.md` | sections B, C and D |
| Prompt versions, failures, fixes | `prompts/prompt_library.md` | |
| Terminal harness `scripts/e2e_test.py` | `eval/runs/` | targets the **first** pipeline; it checks valid JSON and that retrieval returns results, so it measures plumbing and not answer quality |
| `tests/` | | unit tests written for the v2 code nodes; the v3 nodes changed, so do not cite them as covering v3 |

---

## 8. Configuration

| What | Where to change it |
|---|---|
| Models | the `model` field in each HTTP Request node (Router, Vision x2, Recipe parser, Chef: `gemma3:4b`; Text intent, Validator: `qwen2.5:3b`; embeddings: `bge-m3`) |
| Sampling and memory | in the same nodes: `temperature` (0 for the router, vision, text intent and validator; 0.4 for the Chef), `num_ctx` (4096; 8192 for the recipe parser), `keep_alive` (15m) |
| Number of candidates | node *RAG search*: `limit` is 40 for ingredient inputs and 10 otherwise |
| Confidence threshold for detected ingredients | node *Normalize 1*: `c >= 0.6` |
| Rejection of non-food images | node *Parse router*: `not_food` needs confidence 0.6 or more |
| Pantry basics that never count as missing | node *Rank recipes*: the `STAPLES` list (keep `scripts/ranker.py` in sync) |
| Ranking rules | node *Rank recipes* |
| Corpus size and collection name | `python scripts/index_rich.py N [COLLECTION]` (the workflow reads `recipes_rich`) |
| Collection used for search | URL of the node *RAG search* (`recipes_rich`) |
| Message length limit | node *Final answer* (3900 characters for steps, 4000 total) |

---

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Connection refused` from a Python script | Qdrant is not running. `docker compose up -d`, then `curl localhost:6333/collections` |
| n8n cannot reach Ollama (timeout) | Ollama listens on localhost only or a firewall blocks it. Apply 5.2 (`OLLAMA_HOST=0.0.0.0`, ufw rule) and re-test with the `wget` command of 5.4 |
| `docker-credential-desktop` not found | Leftover Docker Desktop config. Reset `~/.docker/config.json` (see 5.1) |
| HTTP node: "Method not allowed" | The node is set to GET. All model and Qdrant calls must be **POST**. Re-import the workflow and reload the browser tab |
| HTTP node: "JSON Body is not valid JSON" | Code was pasted into the wrong field. Re-import the workflow |
| Bot never answers | Check, in this order: the `cloudflared` terminal is still running; `docker compose exec n8n printenv WEBHOOK_URL` equals the tunnel address; the workflow is published (Unpublish, then Publish to re-register); the Executions tab shows whether a run started |
| "n8n can't listen for test executions at the same time as production ones" | The workflow is published. Unpublish it before using Execute workflow |
| Telegram 400 "can't parse entities" | Markdown characters in the message. The code nodes already strip them; if you edit those nodes, keep that step |
| "Analyzing..." arrives after the answer | n8n runs the top-most branch first. Keep the progress message node above the Input Type branch |
| `model not found` | `ollama pull gemma3:4b`, `ollama pull qwen2.5:3b`, `ollama pull bge-m3` |
| Very slow answers | CPU inference, one to several minutes per request is normal. Use smaller photos, or a GPU |
| "That image does not look like food" on a real food photo | The router was confident it was not food. Send a clearer, closer photo; check the Router output in Executions |
| A photo is ignored or gets the help message | Photos sent as files (documents) are not read. Send it as a normal photo |
| No result or an odd recipe | The knowledge base holds about 60,000 recipes. Try other ingredients or remove the time limit; a filter on cooking time or vegetarian can leave few candidates |
| Substitutions are missing from the answer | The validator rejected them or its verdict could not be read (they fail closed). Look at the *Validator* output in Executions |

---

## 10. Known limits

- Retrieval was evaluated on only 10 queries, and ingredient matching on simulated users. Real photos and typed lists are messier.
- Ingredient names come from the vision model (`gemma3:4b`) and can be wrong or incomplete on dark, blurry or crowded photos. Low-confidence items are reported to the user as "not sure about".
- The corpus is English. Other languages are translated, but regional dishes may have no close recipe; the answer then says it is the closest match.
- Recipe screenshots are shown as extracted; the small vision model can misread quantities. Screenshots now also go through retrieval, the Chef and the Validator, which makes them slower.
- The 3B validator was wrong on counting, list comparison and grounding in earlier versions. It now judges substitutions, intro and tip, and substitutions fail closed, so a validator mistake costs a missing suggestion. Its drop rate is measured in `eval/e2e_tests.md` section D.
- The Telegram bot works only while the laptop, Docker, Ollama and the tunnel are running. The tunnel address changes at every restart.
- No nutrition data, no allergen checks, no fine-tuning.

---

## 11. Where each course requirement lives

| Requirement | Where |
|---|---|
| Automation platform, triggered end to end | `workflows/recipe-helper-telegram-v3.json` (n8n, started by a Telegram message) |
| Prompt engineering, versioned library, failures, before/after | `prompts/prompt_library.md`, `eval/e2e_tests.md`, `report/report.md` section 2 |
| RAG: corpus, chunking comparison, embeddings, store, retrieval, evaluation | `scripts/index.py`, `scripts/index_rich.py`, `scripts/eval.py`, `scripts/eval_ingredients.py`, `eval/`, `report/report.md` section 3 |
| Multi-agent system and its justification | `report/report.md` section 4, section 2 of this file |
| Multimodality (photos and screenshots) | `report/report.md` section 5, nodes *Router*, *Vision ingredients*, *Vision dish*, *Recipe parser* |
| Technical report | `report/report.md` |

---

## 12. Security and data

- The Telegram token and the n8n password are never stored in the repository. Credentials live in n8n only; the optional `.env` token (for `start.sh`) is git-ignored. If a password was shared or exposed while working, change it (n8n: Settings → Personal).
- `.gitignore` excludes `.venv/`, `data/RAW_recipes.csv`, `.env`, `.tunnel.pid` and `.tunnel.log`.
- Local processing: photos are handled by Ollama on your machine, with no cloud model. Telegram itself receives and stores the messages, as with any bot, and n8n keeps an execution history (delete it after a demo if it contains personal photos).
- Models only return JSON that code parses inside try/catch; they cannot call tools or run code, so text hidden in an image can at worst change the wording of a recipe.
- Qdrant is published on `127.0.0.1` only; Ollama listens on all interfaces so that the container can reach it, so keep the ufw rule of 5.2 and block port 11434 from outside.
- The public tunnel exposes the whole n8n address, including its login page: use a strong password and stop the tunnel (`./stop.sh`) when you are not demoing.
- Dataset: Food.com Recipes and Interactions (Majumder, Li, Ni, McAuley, *Generating Personalized Recipes from Historical User Preferences*, EMNLP 2019). Data files remain the property of their original authors; this project uses them for coursework only and does not redistribute them.
