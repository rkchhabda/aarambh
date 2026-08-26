#!/usr/bin/env bash
# Deploy Quant Signal Platform (API + Dashboard)
# Usage: ./deploy.sh [build|up|down|logs]

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
    echo ""
    echo "📝 Test API: curl -H 'X-API-Key: qs_hvw4wTe3mRaRruyVXxmT1fcgWRiZKXG-1aMbeOO9' \\"
    echo "             -H 'Content-Type: application/json' \\"
    echo "             -d '{\"ticker\":\"AAPL\"}' http://localhost:8000/v1/signal"
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
    echo "Usage: $0 {build|up|down|logs|restart}"
    exit 1
    ;;
esac