#!/bin/bash

# Festival Playlist Generator - Stop Script
# This script stops all services and optionally cleans up

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_DIR="$PROJECT_ROOT/services/api"

echo "🛑 Stopping Festival Playlist Generator..."
echo "=================================="

# Check if docker-compose.yml exists
if [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in $COMPOSE_DIR"
    echo "💡 Services may not be running with Docker Compose"
    exit 1
fi

# Change to the compose directory
cd "$COMPOSE_DIR"

# Parse command line arguments
CLEANUP=false
REMOVE_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --remove-data)
            REMOVE_DATA=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cleanup      Remove containers and networks"
            echo "  --remove-data  Remove containers, networks, and volumes (WARNING: This deletes all data!)"
            echo "  -h, --help     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Stop services
echo "⏹️  Stopping services..."
docker-compose stop

if [ "$CLEANUP" = true ] || [ "$REMOVE_DATA" = true ]; then
    echo "🧹 Removing containers and networks..."
    docker-compose down
fi

if [ "$REMOVE_DATA" = true ]; then
    echo "⚠️  WARNING: Removing all data volumes..."
    read -p "Are you sure you want to delete all data? This cannot be undone! (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose down -v
        echo "🗑️  All data has been removed"
    else
        echo "❌ Data removal cancelled"
    fi
fi

echo ""
echo "✅ Festival Playlist Generator stopped successfully!"

if [ "$CLEANUP" = false ] && [ "$REMOVE_DATA" = false ]; then
    echo ""
    echo "💡 Tips:"
    echo "   - Use './scripts/stop.sh --cleanup' to remove containers"
    echo "   - Use './scripts/stop.sh --remove-data' to remove all data (WARNING: destructive!)"
    echo "   - Use './scripts/start.sh' to start services again"
fi