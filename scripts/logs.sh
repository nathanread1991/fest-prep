#!/bin/bash

# Festival Playlist Generator - Logs Script
# This script shows logs from various services

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$PROJECT_ROOT/services/api"

echo "📝 Festival Playlist Generator Logs"
echo "=================================="

# Check if docker-compose.yml exists
if [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in $COMPOSE_DIR"
    exit 1
fi

# Change to the compose directory
cd "$COMPOSE_DIR"

# Parse command line arguments
SERVICE=""
FOLLOW=false
TAIL_LINES=50

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -s, --service SERVICE  Show logs for specific service (app, postgres, redis, celery_worker, celery_beat)"
            echo "  -f, --follow          Follow log output"
            echo "  -n, --tail LINES      Number of lines to show (default: 50)"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    Show recent logs from all services"
            echo "  $0 -f                 Follow logs from all services"
            echo "  $0 -s app -f          Follow logs from FastAPI app only"
            echo "  $0 -s celery_worker   Show recent logs from Celery worker"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build docker-compose logs command
LOGS_CMD="docker-compose logs"

if [ "$FOLLOW" = true ]; then
    LOGS_CMD="$LOGS_CMD -f"
fi

LOGS_CMD="$LOGS_CMD --tail=$TAIL_LINES"

if [ -n "$SERVICE" ]; then
    LOGS_CMD="$LOGS_CMD $SERVICE"
    echo "📋 Showing logs for service: $SERVICE"
else
    echo "📋 Showing logs for all services"
fi

if [ "$FOLLOW" = true ]; then
    echo "👀 Following logs (Press Ctrl+C to stop)..."
else
    echo "📄 Showing last $TAIL_LINES lines..."
fi

echo ""

# Execute the logs command
eval $LOGS_CMD