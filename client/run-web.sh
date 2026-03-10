#!/usr/bin/env bash
# Builds (if needed) and starts the Expo web container detached.
# Usage:
#   ./client/run-web.sh                  # start (or restart) the container
#   ./client/run-web.sh --rebuild        # force image rebuild before starting
#   ./client/run-web.sh --stop           # stop and remove the container

set -euo pipefail

CONTAINER_NAME="qgen_expo_web"
IMAGE_NAME="qgen_expo_web"
CLIENT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load env vars from .env.local if it exists
ENV_FILE="$CLIENT_DIR/../.env.local"
EXPO_PUBLIC_PRODUCTION_API_URL="${EXPO_PUBLIC_PRODUCTION_API_URL:-http://localhost:8000/api/v1}"
EXPO_PUBLIC_USE_PRODUCTION_API="${EXPO_PUBLIC_USE_PRODUCTION_API:-false}"
# Don't source .env.local for web — it contains mobile-specific vars (DEV_MACHINE_IP, USE_SIMULATOR)
# that break Metro. If you need other .env.local vars, add them explicitly here.
if [[ -f "$ENV_FILE" ]]; then
  # Root .env.local stores keys without EXPO_PUBLIC_ prefix (sync-env.js adds it for native builds)
  # Try both forms so this works whether ENV_FILE is the root or client .env.local
  _val="$(grep -E '^EXPO_PUBLIC_PRODUCTION_API_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  [[ -z "$_val" ]] && _val="$(grep -E '^PRODUCTION_API_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  [[ -n "$_val" ]] && EXPO_PUBLIC_PRODUCTION_API_URL="$_val"

  _val="$(grep -E '^EXPO_PUBLIC_USE_PRODUCTION_API=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  [[ -z "$_val" ]] && _val="$(grep -E '^USE_PRODUCTION_API=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  [[ -n "$_val" ]] && EXPO_PUBLIC_USE_PRODUCTION_API="$_val"
fi

stop_container() {
  if docker container inspect "$CONTAINER_NAME" &>/dev/null; then
    echo "Stopping and removing $CONTAINER_NAME..."
    docker stop "$CONTAINER_NAME" && docker rm "$CONTAINER_NAME"
  fi
}

if [[ "${1:-}" == "--stop" ]]; then
  stop_container
  echo "Done."
  exit 0
fi

# Rebuild image if requested or if it doesn't exist yet
if [[ "${1:-}" == "--rebuild" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
  echo ""
  echo "The following env vars will be baked into the static build:"
  echo "  EXPO_PUBLIC_PRODUCTION_API_URL  = $EXPO_PUBLIC_PRODUCTION_API_URL"
  echo "  EXPO_PUBLIC_USE_PRODUCTION_API  = $EXPO_PUBLIC_USE_PRODUCTION_API"
  echo ""
  read -rp "Proceed with build? [y/N] " confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
  echo "Building image $IMAGE_NAME ..."
  docker build \
    --build-arg "EXPO_PUBLIC_PRODUCTION_API_URL=$EXPO_PUBLIC_PRODUCTION_API_URL" \
    --build-arg "EXPO_PUBLIC_USE_PRODUCTION_API=$EXPO_PUBLIC_USE_PRODUCTION_API" \
    -t "$IMAGE_NAME" "$CLIENT_DIR"
fi

# Remove existing container so we can recreate it cleanly
stop_container

echo "Starting $CONTAINER_NAME on port 8081..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p 8081:8081 \
  --memory 1g \
  --memory-reservation 256m \
  "$IMAGE_NAME"

echo "$CONTAINER_NAME is running. Logs: docker logs -f $CONTAINER_NAME"
