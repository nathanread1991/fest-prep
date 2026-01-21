@echo off
REM Festival Playlist Generator - Stop Script (Windows)
REM This script stops all services and optionally cleans up

setlocal enabledelayedexpansion

echo 🛑 Stopping Festival Playlist Generator...
echo ==================================

REM Parse command line arguments
set CLEANUP=false
set REMOVE_DATA=false

:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--cleanup" (
    set CLEANUP=true
    shift
    goto :parse_args
)
if "%~1"=="--remove-data" (
    set REMOVE_DATA=true
    shift
    goto :parse_args
)
if "%~1"=="-h" goto :show_help
if "%~1"=="--help" goto :show_help
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:show_help
echo Usage: %0 [OPTIONS]
echo.
echo Options:
echo   --cleanup      Remove containers and networks
echo   --remove-data  Remove containers, networks, and volumes (WARNING: This deletes all data!)
echo   -h, --help     Show this help message
exit /b 0

:args_done

REM Stop services
echo ⏹️  Stopping services...
docker-compose stop

if "%CLEANUP%"=="true" (
    echo 🧹 Removing containers and networks...
    docker-compose down
)

if "%REMOVE_DATA%"=="true" (
    echo ⚠️  WARNING: Removing all data volumes...
    set /p "confirm=Are you sure you want to delete all data? This cannot be undone! (y/N): "
    if /i "!confirm!"=="y" (
        docker-compose down -v
        echo 🗑️  All data has been removed
    ) else (
        echo ❌ Data removal cancelled
    )
)

echo.
echo ✅ Festival Playlist Generator stopped successfully!

if "%CLEANUP%"=="false" (
    if "%REMOVE_DATA%"=="false" (
        echo.
        echo 💡 Tips:
        echo    - Use 'scripts\stop.bat --cleanup' to remove containers
        echo    - Use 'scripts\stop.bat --remove-data' to remove all data (WARNING: destructive!)
        echo    - Use 'scripts\start.bat' to start services again
    )
)