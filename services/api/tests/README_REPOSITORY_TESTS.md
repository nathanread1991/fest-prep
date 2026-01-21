# Repository Tests Documentation

## Overview

Comprehensive unit tests have been created for all repository classes in `test_repositories.py`. The test suite includes 42 tests covering:

- **BaseRepository**: Generic CRUD operations (12 tests)
- **ArtistRepository**: Artist-specific queries (8 tests)
- **FestivalRepository**: Festival-specific queries (4 tests)
- **PlaylistRepository**: Playlist-specific queries (9 tests)
- **SetlistRepository**: Setlist-specific queries (4 tests)
- **UserRepository**: User-specific queries (5 tests)

## Test Coverage

The tests cover:
- ✅ CRUD operations (Create, Read, Update, Delete)
- ✅ Bulk operations
- ✅ Pagination and filtering
- ✅ Search functionality
- ✅ Relationship loading
- ✅ Count and exists operations
- ✅ Custom repository methods

## Testing Approach

**PostgreSQL Testcontainers** - The tests use testcontainers to spin up a real PostgreSQL database in Docker for testing. This provides:
- ✅ Realistic testing with actual PostgreSQL (same as production Aurora)
- ✅ Automatic setup and teardown
- ✅ Isolated test environment
- ✅ No manual database configuration needed

## Prerequisites

1. **Docker** must be running
2. **Install test dependencies**:
   ```bash
   pip install testcontainers[postgresql]
   ```

## Running the Tests

```bash
# Run all repository tests
pytest services/api/tests/test_repositories.py -v

# Run specific test class
pytest services/api/tests/test_repositories.py::TestArtistRepository -v

# Run with coverage
pytest services/api/tests/test_repositories.py --cov=festival_playlist_generator/repositories --cov-report=term-missing

# Run a single test
pytest services/api/tests/test_repositories.py::TestArtistRepository::test_get_by_name -v
```

## How It Works

1. **Session-scoped container**: A PostgreSQL container starts once for all tests
2. **Fresh database**: Tables are created at the start of the test session
3. **Test isolation**: Each test gets a fresh session with automatic rollback
4. **Automatic cleanup**: Container is destroyed after all tests complete

## Test Structure

### Fixtures (conftest.py)
- `postgres_container`: PostgreSQL testcontainer (session-scoped)
- `async_engine`: Database engine connected to container
- `async_session`: Database session with automatic rollback
- `*_repository`: Repository instances
- `sample_*`: Pre-created test data

### Test Classes
Each repository has its own test class with focused tests for its specific methods.

### Test Naming Convention
- `test_<method_name>_<scenario>`: Clear description of what's being tested
- Example: `test_get_by_id_found`, `test_search_paginated_by_name`

## Coverage Goals

Target: **90%+ coverage** for repository layer

Current test coverage areas:
- ✅ Happy path scenarios
- ✅ Not found scenarios
- ✅ Pagination edge cases
- ✅ Bulk operations
- ✅ Search and filtering
- ✅ Relationship loading

## Troubleshooting

### Docker not running
```
Error: Cannot connect to the Docker daemon
```
**Solution**: Start Docker Desktop or Docker daemon

### Port conflicts
```
Error: Port 5432 is already in use
```
**Solution**: Testcontainers automatically finds an available port. If issues persist, stop other PostgreSQL instances.

### Slow first run
The first test run downloads the PostgreSQL Docker image (~80MB). Subsequent runs are much faster.

## Notes

- All tests use async/await patterns
- Tests are isolated (each test gets fresh database state)
- Fixtures handle setup and teardown automatically
- Tests follow AAA pattern (Arrange, Act, Assert)
- Container is reused across tests for performance
