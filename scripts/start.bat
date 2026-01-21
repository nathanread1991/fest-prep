@echo off
REM Festival Playlist Generator - Start Script (Windows)
REM This script starts all services using Docker Compose

echo 🎵 Starting Festival Playlist Generator...
echo ==================================

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker is not running. Please start Docker first.
    exit /b 1
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: docker-compose is not installed or not in PATH.
    exit /b 1
)

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Start services
echo 🚀 Starting services...
docker-compose up -d

REM Wait for services to be ready
echo ⏳ Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check service health
echo 🔍 Checking service health...

REM Check PostgreSQL
docker-compose exec -T postgres pg_isready -U festival_user -d festival_db >nul 2>&1
if errorlevel 1 (
    echo ⚠️  PostgreSQL is starting up...
) else (
    echo ✅ PostgreSQL is ready
)

REM Check Redis
docker-compose exec -T redis redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Redis is starting up...
) else (
    echo ✅ Redis is ready
)

REM Check if FastAPI app is responding
echo ⏳ Waiting for FastAPI application...
for /l %%i in (1,1,30) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if not errorlevel 1 (
        echo ✅ FastAPI application is ready
        goto :app_ready
    )
    if %%i==30 (
        echo ⚠️  FastAPI application is still starting up...
    )
    timeout /t 2 /nobreak >nul
)
:app_ready

echo.
echo 🎉 Festival Playlist Generator is starting up!
echo ==================================
echo 📱 Web Interface: http://localhost:8000
echo 📚 API Documentation: http://localhost:8000/docs
echo 🔍 Health Check: http://localhost:8000/health
echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo 📝 To view logs: scripts\logs.bat
echo 🛑 To stop services: scripts\stop.bat