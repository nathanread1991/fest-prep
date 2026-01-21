#!/bin/bash

# Festival Playlist Generator - Development Script
# This script provides development utilities

set -e  # Exit on any error

echo "🛠️  Festival Playlist Generator Development Tools"
echo "=============================================="

# Parse command line arguments
COMMAND=""

while [[ $# -gt 0 ]]; do
    case $1 in
        test)
            COMMAND="test"
            shift
            ;;
        migrate)
            COMMAND="migrate"
            shift
            ;;
        shell)
            COMMAND="shell"
            shift
            ;;
        reset-db)
            COMMAND="reset-db"
            shift
            ;;
        format)
            COMMAND="format"
            shift
            ;;
        lint)
            COMMAND="lint"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 COMMAND"
            echo ""
            echo "Commands:"
            echo "  test       Run all tests"
            echo "  migrate    Run database migrations"
            echo "  shell      Open Python shell in app container"
            echo "  reset-db   Reset database (WARNING: destructive!)"
            echo "  format     Format code with black and isort"
            echo "  lint       Run linting checks"
            echo "  -h, --help Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown command: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    echo "❌ No command specified. Use --help for usage information"
    exit 1
fi

case $COMMAND in
    test)
        echo "🧪 Running tests..."
        docker-compose exec app pytest tests/ -v
        ;;
    migrate)
        echo "🗄️  Running database migrations..."
        docker-compose exec app alembic upgrade head
        ;;
    shell)
        echo "🐍 Opening Python shell..."
        docker-compose exec app python3 -c "
import sys
sys.path.append('/app')
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models import *
print('Festival Playlist Generator Python Shell')
print('Available imports: get_db, models.*')
print('Database URL: postgresql://festival_user:festival_pass@postgres:5432/festival_db')
"
        docker-compose exec app python3
        ;;
    reset-db)
        echo "⚠️  WARNING: This will delete all data in the database!"
        read -p "Are you sure you want to reset the database? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Resetting database..."
            docker-compose exec postgres psql -U festival_user -d festival_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
            echo "🗄️  Running migrations..."
            docker-compose exec app alembic upgrade head
            echo "✅ Database reset complete"
        else
            echo "❌ Database reset cancelled"
        fi
        ;;
    format)
        echo "🎨 Formatting code..."
        docker-compose exec app black festival_playlist_generator/ tests/
        docker-compose exec app isort festival_playlist_generator/ tests/
        echo "✅ Code formatting complete"
        ;;
    lint)
        echo "🔍 Running linting checks..."
        echo "Running flake8..."
        docker-compose exec app flake8 festival_playlist_generator/ tests/ || true
        echo "Running mypy..."
        docker-compose exec app mypy festival_playlist_generator/ || true
        echo "✅ Linting checks complete"
        ;;
esac