#!/usr/bin/env bash
# Deploy Quant Signal Platform (API + Dashboard)
# Usage: ./deploy.sh [build|up|down|logs|restart|push]

set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
ACTION="${1:-up}"

case "$ACTION" in
  build)
    echo "🔨 Building images..."
    docker compose -f "$COMPOSE_FILE" build --no-cache
    ;;
  up)
    echo "🚀 Starting services..."
    docker compose -f "$COMPOSE_FILE" up -d
    echo "⏳ Waiting for API health check..."
    sleep 5
    for i in {1..30}; do
      if curl -sf http://localhost:8000/health >/dev/null; then
        echo "✅ API is healthy!"
        break
      fi
      sleep 2
    done
    echo ""
    echo "🌐 Services running:"
    echo "   API:       http://localhost:8000"
    echo "   Dashboard: http://localhost:8501"
    ;;
  push)
    echo "📤 Committing and pushing to origin main (triggers Render auto-deploy)..."
    git add .
    git commit -m "deploy: automated push for Render auto-deploy" || true
    git push origin main
    echo "✅ Pushed to main. Render is automatically building and deploying!"
    ;;
  down)
    echo "🛑 Stopping services..."
    docker compose -f "$COMPOSE_FILE" down
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
    ;;
  restart)
    echo "🔄 Restarting..."
    docker compose -f "$COMPOSE_FILE" restart
    ;;
  *)
    echo "Usage: $0 {build|up|down|logs|restart|push}"
    exit 1
    ;;
esac