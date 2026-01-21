# Festival Playlist Generator - Utility Scripts

This directory contains utility scripts to help you manage the Festival Playlist Generator application.

## Quick Start

### Unix/macOS/Linux
```bash
# Start the application
./festival.sh start

# Check status
./festival.sh status

# View logs
./festival.sh logs

# Stop the application
./festival.sh stop
```

### Windows
```cmd
# Start the application
festival.bat start

# Check status
festival.bat status

# View logs
festival.bat logs

# Stop the application
festival.bat stop
```

## Available Scripts

### Main Entry Points
- `festival.sh` / `festival.bat` - Main utility script with all commands
- Provides a unified interface for all operations

### Individual Scripts (Unix/macOS/Linux)
- `start.sh` - Start all services with health checks
- `stop.sh` - Stop services with optional cleanup
- `status.sh` - Show current status of all services
- `logs.sh` - View and follow service logs
- `dev.sh` - Development utilities (tests, migrations, etc.)

### Individual Scripts (Windows)
- `start.bat` - Start all services with health checks
- `stop.bat` - Stop services with optional cleanup

## Common Commands

### Starting the Application
```bash
./festival.sh start
```
This will:
- Start PostgreSQL, Redis, FastAPI app, and Celery workers
- Wait for services to be healthy
- Show service status and URLs

### Viewing Logs
```bash
# View recent logs from all services
./festival.sh logs

# Follow logs in real-time
./festival.sh logs -f

# View logs from specific service
./festival.sh logs -s app
./festival.sh logs -s celery_worker
```

### Checking Status
```bash
./festival.sh status
```
Shows:
- Container status
- Health check results
- Resource usage
- Service URLs

### Development Commands
```bash
# Run tests
./festival.sh test

# Run database migrations
./festival.sh migrate

# Open Python shell with app context
./festival.sh shell

# Format code
./festival.sh format

# Run linting
./festival.sh lint

# Reset database (WARNING: destructive!)
./festival.sh reset-db
```

### Stopping the Application
```bash
# Stop services (containers remain)
./festival.sh stop

# Stop and remove containers/networks
./festival.sh stop --cleanup

# Stop and remove everything including data (WARNING: destructive!)
./festival.sh stop --remove-data
```

## Service URLs

When running, the application provides these endpoints:
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Troubleshooting

### Docker Issues
If you get Docker-related errors:
1. Make sure Docker Desktop is running
2. Check if you have sufficient resources allocated to Docker
3. Try restarting Docker Desktop

### Port Conflicts
If ports 5432, 6379, or 8000 are already in use:
1. Stop other services using those ports
2. Or modify the ports in `docker-compose.yml`

### Permission Issues (Unix/macOS/Linux)
If you get permission denied errors:
```bash
chmod +x festival.sh scripts/*.sh
```

### Database Issues
If you encounter database problems:
```bash
# Reset the database (WARNING: deletes all data)
./festival.sh reset-db

# Or restart with cleanup
./festival.sh stop --cleanup
./festival.sh start
```

### Web Interface Not Accessible
If you can't access http://localhost:8000:

1. **Check if containers are running**:
   ```bash
   ./festival.sh status
   ```

2. **Check application logs**:
   ```bash
   ./festival.sh logs -s app
   ```

3. **Common fixes**:
   - **Missing dependencies**: If you see `ModuleNotFoundError`, rebuild the containers:
     ```bash
     ./festival.sh stop --cleanup
     ./festival.sh start
     ```
   - **Port conflicts**: Make sure port 8000 isn't used by another service
   - **Database connection issues**: Ensure PostgreSQL is healthy in the status output

4. **Test the health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```
   Should return: `{"success":true,"status":"healthy",...}`

5. **If the build fails**, check for:
   - Sufficient disk space
   - Docker daemon running
   - Network connectivity for downloading dependencies

## Development Workflow

1. **Start the application**: `./festival.sh start`
2. **Make code changes** in your editor
3. **Run tests**: `./festival.sh test`
4. **Check logs**: `./festival.sh logs -f`
5. **Format code**: `./festival.sh format`
6. **Stop when done**: `./festival.sh stop`

The FastAPI application runs with auto-reload enabled, so code changes are automatically picked up without restarting.