#!/bin/bash

# Festival Playlist Generator - Start Script
# This script starts all services using Docker Compose

set -e  # Exit on any error

echo "🎵 Starting Festival Playlist Generator..."
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ Error: docker-compose is not installed or not in PATH."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo "🔍 Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U festival_user -d festival_db > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "⚠️  PostgreSQL is starting up..."
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "⚠️  Redis is starting up..."
fi

# Check if FastAPI app is responding
echo "⏳ Waiting for FastAPI application..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ FastAPI application is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  FastAPI application is still starting up..."
    fi
    sleep 2
done

echo ""
echo "🎉 Festival Playlist Generator is starting up!"
echo "=================================="
echo "📱 Web Interface: http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "🔍 Health Check: http://localhost:8000/health"
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "📝 To view logs: ./scripts/logs.sh"
echo "🛑 To stop services: ./scripts/stop.sh"