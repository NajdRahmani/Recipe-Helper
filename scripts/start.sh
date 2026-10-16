#!/usr/bin/env bash
# Starts everything for Recipe Helper: Docker, Ollama, public tunnel, n8n, Qdrant.
# Usage: ./start.sh [--no-warmup]
# Optional: put TELEGRAM_BOT_TOKEN=... in a .env file (git-ignored) to let the script verify the webhook.
cd "$(dirname "$0")" || exit 1

OK="[ok]"; WARN="[!!]"; INFO="[..]"
ok()   { echo "$OK   $*"; }
warn() { echo "$WARN   $*"; }
info() { echo "$INFO   $*"; }

WARMUP=1
[ "${1:-}" = "--no-warmup" ] && WARMUP=0

# 1) Docker and Ollama services
for svc in docker ollama; do
  if systemctl is-active --quiet "$svc"; then ok "$svc is running"
  else info "starting $svc (sudo may ask for your password)"; sudo systemctl start "$svc" || warn "could not start $svc"; fi
done

# 2) Ollama must listen on all interfaces so the n8n container can reach it
sleep 1
if ss -tln 2>/dev/null | grep ':11434' | grep -qE '(\*|0\.0\.0\.0|\[::\]):11434'; then
  ok "Ollama listens on all interfaces"
else
  warn "Ollama listens on localhost only. Fix: see README section 5.2 (OLLAMA_HOST=0.0.0.0), then rerun"
fi

# 3) Public tunnel for the Telegram webhook
if ! command -v cloudflared >/dev/null 2>&1; then
  warn "cloudflared not installed (see README 5.6). Continuing without a public URL: Telegram will not work"
  URL="http://localhost:5678"
else
  if [ -f .tunnel.pid ] && kill -0 "$(cat .tunnel.pid)" 2>/dev/null; then
    info "stopping the previous tunnel"; kill "$(cat .tunnel.pid)" 2>/dev/null; sleep 1
  fi
  : > .tunnel.log
  nohup cloudflared tunnel --url http://localhost:5678 > .tunnel.log 2>&1 &
  echo $! > .tunnel.pid
  info "starting the tunnel..."
  URL=""
  for _ in $(seq 1 40); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' .tunnel.log | head -n1)
    [ -n "$URL" ] && break
    sleep 1
  done
  if [ -z "$URL" ]; then warn "no tunnel address found, see .tunnel.log"; URL="http://localhost:5678"
  else ok "tunnel: $URL"; fi
fi

# 4) n8n and Qdrant with the tunnel address
info "starting n8n and Qdrant"
WEBHOOK_URL="$URL" docker compose up -d >/dev/null 2>&1 || { warn "docker compose failed, run: docker compose up -d"; exit 1; }

info "waiting for n8n..."
for _ in $(seq 1 60); do curl -fs http://localhost:5678/healthz >/dev/null 2>&1 && break; sleep 1; done
curl -fs http://localhost:5678/healthz >/dev/null 2>&1 && ok "n8n is up: http://localhost:5678" || warn "n8n did not answer, check: docker compose logs n8n"

for _ in $(seq 1 30); do curl -fs http://localhost:6333/collections >/dev/null 2>&1 && break; sleep 1; done
if curl -fs http://localhost:6333/collections >/tmp/rh_collections.json 2>/dev/null; then
  ok "Qdrant is up"
  grep -q '"recipes_rich"' /tmp/rh_collections.json && ok "collection recipes_rich exists" \
    || warn "collection recipes_rich is missing. Run: source .venv/bin/activate && python scripts/index_rich.py"
else
  warn "Qdrant did not answer"
fi

# 5) Models and container-to-Ollama connection
for m in gemma3:4b qwen2.5:3b bge-m3; do
  ollama list 2>/dev/null | grep -q "^$m" && ok "model $m present" || warn "model $m missing. Run: ollama pull $m"
done
if docker compose exec -T n8n wget -qO- --timeout=5 http://host.docker.internal:11434/api/tags >/dev/null 2>&1; then
  ok "n8n container can reach Ollama"
else
  warn "n8n container cannot reach Ollama (firewall or OLLAMA_HOST). See README 9"
fi

# 6) Warm up the models in the background (first call is slow otherwise)
if [ "$WARMUP" = 1 ]; then
  for m in gemma3:4b qwen2.5:3b; do
    ( curl -s http://localhost:11434/api/generate -d "{\"model\":\"$m\",\"prompt\":\"hi\",\"stream\":false,\"keep_alive\":\"30m\"}" >/dev/null 2>&1 & )
  done
  info "warming up models in the background (30 min keep-alive)"
fi

# 7) Telegram webhook check (needs TELEGRAM_BOT_TOKEN in .env)
TOKEN=""
[ -f .env ] && TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'")
HOST=$(echo "$URL" | sed -E 's#https?://##')
if [ -n "$TOKEN" ] && [ "$URL" != "http://localhost:5678" ]; then
  info "checking the Telegram webhook (up to 40 s)"
  MATCH=0
  for _ in $(seq 1 20); do
    INFO_JSON=$(curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo")
    echo "$INFO_JSON" | grep -q "$HOST" && { MATCH=1; break; }
    sleep 2
  done
  if [ "$MATCH" = 1 ]; then ok "Telegram webhook points to the new tunnel"
  else warn "Telegram webhook does not point to $HOST yet. In n8n: Unpublish then Publish recipe-helper-telegram-v2"; fi
fi

echo
echo "------------------------------------------------------------"
echo " n8n:        http://localhost:5678"
echo " Public URL: $URL"
echo " Next:       open n8n, check recipe-helper-telegram-v2 is Published,"
[ -z "$TOKEN" ] && echo "             and if the bot is silent: Unpublish, then Publish again."
echo " Stop:       ./stop.sh"
echo "------------------------------------------------------------"
