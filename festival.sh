#!/bin/bash

# Festival Playlist Generator - Main Utility Script
# This is the main entry point for managing the application

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

show_banner() {
    echo -e "${PURPLE}"
    echo "🎵 Festival Playlist Generator"
    echo "=============================="
    echo -e "${NC}"
}

show_help() {
    show_banner
    echo "Usage: $0 COMMAND [OPTIONS]"
    echo ""
    echo -e "${CYAN}Main Commands:${NC}"
    echo "  start          Start all services"
    echo "  stop           Stop all services"
    echo "  restart        Restart all services"
    echo "  status         Show service status"
    echo "  logs           Show service logs"
    echo ""
    echo -e "${CYAN}Development Commands:${NC}"
    echo "  test           Run tests"
    echo "  migrate        Run database migrations"
    echo "  shell          Open Python shell"
    echo "  reset-db       Reset database (destructive!)"
    echo "  format         Format code"
    echo "  lint           Run linting"
    echo "  typecheck      Run mypy type checking"
    echo ""
    echo -e "${CYAN}Options for stop:${NC}"
    echo "  --cleanup      Remove containers and networks"
    echo "  --remove-data  Remove all data (WARNING: destructive!)"
    echo ""
    echo -e "${CYAN}Options for logs:${NC}"
    echo "  -f, --follow   Follow log output"
    echo "  -s SERVICE     Show logs for specific service"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 start                    # Start all services"
    echo "  $0 logs -f                  # Follow all logs"
    echo "  $0 logs -s app              # Show app logs only"
    echo "  $0 stop --cleanup           # Stop and cleanup"
    echo "  $0 test                     # Run tests"
}

# Parse command
COMMAND="$1"
shift || true

case "$COMMAND" in
    start)
        show_banner
        # Check if Docker Compose configuration exists
        if [ -f "$SCRIPT_DIR/services/api/docker-compose.yml" ]; then
            # Check if Docker is available
            if command -v docker > /dev/null 2>&1 && docker info > /dev/null 2>&1; then
                echo -e "${GREEN}Using Docker Compose...${NC}"
                exec "$SCRIPT_DIR/scripts/start.sh"
            else
                echo -e "${RED}❌ docker-compose.yml found but Docker is not running${NC}"
                echo -e "${YELLOW}Starting services locally instead...${NC}"
                exec "$SCRIPT_DIR/scripts/start-local.sh"
            fi
        else
            echo -e "${YELLOW}No docker-compose.yml found, starting services locally...${NC}"
            exec "$SCRIPT_DIR/scripts/start-local.sh"
        fi
        ;;
    stop)
        show_banner
        exec "$SCRIPT_DIR/scripts/stop.sh" "$@"
        ;;
    restart)
        show_banner
        echo -e "${YELLOW}Restarting Festival Playlist Generator...${NC}"
        "$SCRIPT_DIR/scripts/stop.sh"
        echo ""
        "$SCRIPT_DIR/scripts/start.sh"
        ;;
    status)
        show_banner
        exec "$SCRIPT_DIR/scripts/status.sh"
        ;;
    logs)
        show_banner
        exec "$SCRIPT_DIR/scripts/logs.sh" "$@"
        ;;
    test|migrate|shell|reset-db|format|lint|typecheck)
        show_banner
        exec "$SCRIPT_DIR/scripts/dev.sh" "$COMMAND" "$@"
        ;;
    -h|--help|help|"")
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac