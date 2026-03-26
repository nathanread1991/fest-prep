#!/bin/bash

# Festival Playlist Generator - Development Script
# This script provides development utilities

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/services/api"
VENV_DIR="$PROJECT_ROOT/venv"

echo "🛠️  Festival Playlist Generator Development Tools"
echo "=============================================="

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found at $VENV_DIR"
    echo "Please run setup.sh first"
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

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
        typecheck)
            COMMAND="typecheck"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 COMMAND"
            echo ""
            echo "Commands:"
            echo "  test       Run all tests"
            echo "  migrate    Run database migrations"
            echo "  shell      Open Python shell"
            echo "  reset-db   Reset database (WARNING: destructive!)"
            echo "  format     Format code with black and isort"
            echo "  lint       Run linting checks"
            echo "  typecheck  Run mypy type checking"
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
        cd "$API_DIR"
        python -m pytest tests/ -v
        ;;
    migrate)
        echo "🗄️  Running database migrations..."
        cd "$API_DIR"
        alembic upgrade head
        ;;
    shell)
        echo "🐍 Opening Python shell..."
        cd "$API_DIR"
        python -c "
import sys
sys.path.insert(0, '.')
from festival_playlist_generator.core.database import get_db
from festival_playlist_generator.models import *
print('Festival Playlist Generator Python Shell')
print('Available imports: get_db, models.*')
print('Use Ctrl+D to exit')
"
        python
        ;;
    reset-db)
        echo "⚠️  WARNING: This will delete all data in the database!"
        read -p "Are you sure you want to reset the database? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Resetting database..."
            cd "$API_DIR"
            # Drop and recreate database using alembic
            alembic downgrade base
            alembic upgrade head
            echo "✅ Database reset complete"
        else
            echo "❌ Database reset cancelled"
        fi
        ;;
    format)
        echo "🎨 Formatting code..."
        cd "$API_DIR"
        black festival_playlist_generator/ tests/
        isort festival_playlist_generator/ tests/
        echo "✅ Code formatting complete"
        ;;
    lint)
        echo "🔍 Running linting checks..."
        cd "$API_DIR"
        echo "Running flake8..."
        flake8 festival_playlist_generator/ tests/ --max-line-length=88 --extend-ignore=E203,W503 || true
        echo ""
        echo "Running mypy..."
        python -m mypy festival_playlist_generator/ --config-file=setup.cfg || true
        echo "✅ Linting checks complete"
        ;;
    typecheck)
        echo "🔍 Running mypy type checking..."
        cd "$API_DIR"
        python -m mypy festival_playlist_generator/ --config-file=setup.cfg
        ;;
esac