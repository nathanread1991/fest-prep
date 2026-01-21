#!/bin/bash

# Festival Playlist Generator - Status Script
# This script shows the current status of all services

set -e  # Exit on any error

echo "📊 Festival Playlist Generator Status"
echo "=================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    exit 1
fi

# Show container status
echo "🐳 Container Status:"
docker-compose ps

echo ""
echo "🔍 Service Health Checks:"

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U festival_user -d festival_db > /dev/null 2>&1; then
    echo "✅ PostgreSQL: Healthy"
else
    echo "❌ PostgreSQL: Not ready"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: Healthy"
else
    echo "❌ Redis: Not ready"
fi

# Check FastAPI app
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ FastAPI App: Healthy"
    
    # Get detailed health info
    echo ""
    echo "🏥 Application Health Details:"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Could not parse health response"
else
    echo "❌ FastAPI App: Not responding"
fi

echo ""
echo "🌐 Service URLs:"
echo "   Web Interface: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Health Check: http://localhost:8000/health"

echo ""
echo "💾 Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker-compose ps -q) 2>/dev/null || echo "Could not retrieve resource usage"