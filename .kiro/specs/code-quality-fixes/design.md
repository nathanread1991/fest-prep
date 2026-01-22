# Code Quality Fixes - Design Document

## Overview

This design addresses fixing all code quality issues preventing the CI pipeline from passing. The project enforces strict quality standards through pre-commit hooks and CI checks including gitleaks, black, isort, flake8, and mypy. Currently, multiple files have linting and type checking errors that block merges.

## Architecture

### Quality Check Pipeline
```
Pre-commit Hooks → CI Pipeline → Merge Gate
     ↓                  ↓
  Local Dev         Automated
  Validation        Validation
```

### Tool Chain
1. **Gitleaks**: Secret scanning (blocking)
2. **Black**: Code formatting (auto-fixable)
3. **isort**: Import sorting (auto-fixable)
4. **Flake8**: Linting (manual fixes required)
5. **MyPy**: Type checking in strict mode (manual fixes required)

## Design Decisions

### 1. Fix Strategy: Automated First, Manual Second

**Decision**: Apply automated fixes (black, isort) before manual fixes (flake8, mypy)

**Rationale**:
- Automated tools can fix ~40% of issues instantly
- Reduces manual work and human error
- Ensures consistent formatting before addressing logic issues
- Black and isort changes may resolve some flake8 warnings

**Implementation**:
```bash
# Phase 1: Automated fixes
black festival_playlist_generator/ tests/
isort festival_playlist_generator/ tests/

# Phase 2: Manual fixes
# Fix remaining flake8 errors
# Fix mypy type errors
```

### 2. Flake8 Error Handling Strategy

**Decision**: Fix errors by category in order of impact and ease

**Rationale**:
- Some errors are trivial (F401 unused imports)
- Others require careful refactoring (E722 bare except)
- Batching by type reduces context switching

**Priority Order**:
1. **F401** (unused imports) - Safe removal
2. **F841** (unused variables) - Safe removal or usage
3. **F541** (f-string without placeholders) - Simple conversion
4. **E712** (comparison to True/False) - Simple boolean fix
5. **E203** (whitespace before ':') - Formatting fix
6. **E501** (line too long) - Requires judgment on breaking
7. **F811** (redefinition) - Requires code analysis
8. **E722** (bare except) - Requires exception analysis

### 3. MyPy Type Annotation Strategy

**Decision**: Add explicit type hints rather than using `# type: ignore`

**Rationale**:
- Project uses strict mypy mode
- Type safety is a core requirement
- `# type: ignore` comments mask real issues
- Proper types improve code maintainability

**Approach**:
- Add type parameters to generic types (Redis[bytes], ConnectionPool[bytes])
- Add return type annotations to all functions
- Fix decorator type hints using `typing.ParamSpec` and `typing.Concatenate`
- Remove unused `# type: ignore` comments

### 4. Line Length Handling (E501)

**Decision**: Break long lines at logical boundaries, prioritizing readability

**Rationale**:
- Max line length is 88 characters (Black default)
- Breaking at logical points maintains code clarity
- Some lines may need refactoring (extract variables/functions)

**Guidelines**:
```python
# Bad: Arbitrary break
result = some_function(arg1, arg2,
    arg3, arg4)

# Good: Logical break
result = some_function(
    arg1,
    arg2,
    arg3,
    arg4,
)

# Better: Extract for clarity
params = (arg1, arg2, arg3, arg4)
result = some_function(*params)
```

### 5. Exception Handling (E722)

**Decision**: Replace bare `except:` with specific exception types

**Rationale**:
- Bare except catches SystemExit, KeyboardInterrupt (dangerous)
- Specific exceptions improve error handling
- Makes debugging easier

**Pattern**:
```python
# Before
try:
    risky_operation()
except:
    handle_error()

# After
try:
    risky_operation()
except (ValueError, KeyError, TypeError) as e:
    handle_error(e)
```

## Implementation Plan

### Phase 1: Automated Formatting
1. Run black on all Python files
2. Run isort on all Python files
3. Commit changes

### Phase 2: Flake8 Fixes (by category)
1. Remove unused imports (F401)
2. Remove/use unused variables (F841)
3. Fix f-string issues (F541)
4. Fix boolean comparisons (E712)
5. Fix whitespace issues (E203)
6. Break long lines (E501)
7. Fix redefinitions (F811)
8. Fix bare excepts (E722)

### Phase 3: MyPy Type Fixes
1. Add type parameters to Redis/ConnectionPool
2. Add function return type annotations
3. Fix decorator type hints
4. Fix class inheritance type issues
5. Remove unused type:ignore comments

### Phase 4: Verification
1. Run full CI pipeline locally
2. Verify all checks pass
3. Run test suite
4. Commit final changes

## Testing Strategy

### Unit Tests
- Existing tests must continue to pass
- No new unit tests required (fixing existing code)

### Integration Tests
- Redis integration tests must pass
- GitHub Actions runner must have Redis CLI installed
- Service health checks must pass

### Validation Commands
```bash
# Format check
docker exec festival_app black --check festival_playlist_generator/ tests/

# Import check
docker exec festival_app isort --check festival_playlist_generator/ tests/

# Lint check
docker exec festival_app flake8 festival_playlist_generator/ tests/ \
  --max-line-length=88 --extend-ignore=E203,W503

# Type check
docker exec festival_app python -m mypy festival_playlist_generator/ \
  --config-file=setup.cfg

# Test suite
docker exec festival_app python -m pytest tests/ -v
```

## Correctness Properties

### Property 1.1: All Python files pass Black formatting
**Validates: Requirements 1.1-1.8**

**Property**: For all Python files in `festival_playlist_generator/` and `tests/`, running `black --check` returns exit code 0

**Test Strategy**: Run black in check mode on entire codebase
```python
def test_black_formatting():
    """All Python files must pass black formatting check"""
    result = subprocess.run(
        ["black", "--check", "festival_playlist_generator/", "tests/"],
        capture_output=True
    )
    assert result.returncode == 0, f"Black formatting failed: {result.stderr}"
```

### Property 1.2: All Python files pass isort check
**Validates: Requirements 1.2**

**Property**: For all Python files, imports are sorted according to isort configuration

**Test Strategy**: Run isort in check mode
```python
def test_isort_imports():
    """All Python files must have sorted imports"""
    result = subprocess.run(
        ["isort", "--check", "festival_playlist_generator/", "tests/"],
        capture_output=True
    )
    assert result.returncode == 0, f"Import sorting failed: {result.stderr}"
```

### Property 2.1: No flake8 linting errors
**Validates: Requirements 1.1-1.8**

**Property**: Running flake8 on all Python files produces zero errors

**Test Strategy**: Run flake8 with project configuration
```python
def test_flake8_linting():
    """All Python files must pass flake8 linting"""
    result = subprocess.run(
        [
            "flake8",
            "festival_playlist_generator/",
            "tests/",
            "--max-line-length=88",
            "--extend-ignore=E203,W503"
        ],
        capture_output=True
    )
    assert result.returncode == 0, f"Flake8 errors found: {result.stdout}"
```

### Property 2.2: No mypy type checking errors
**Validates: Requirements 2.1-2.5**

**Property**: Running mypy in strict mode produces zero errors

**Test Strategy**: Run mypy with strict configuration
```python
def test_mypy_type_checking():
    """All Python files must pass mypy type checking"""
    result = subprocess.run(
        [
            "python", "-m", "mypy",
            "festival_playlist_generator/",
            "--config-file=setup.cfg"
        ],
        capture_output=True
    )
    assert result.returncode == 0, f"MyPy errors found: {result.stdout}"
```

### Property 3.1: CI pipeline passes all checks
**Validates: Requirements 3.1-3.3**

**Property**: The complete CI pipeline (gitleaks → black → isort → flake8 → mypy → tests) completes successfully

**Test Strategy**: Run full CI pipeline locally
```python
def test_full_ci_pipeline():
    """Complete CI pipeline must pass"""
    checks = [
        ["pre-commit", "run", "--all-files"],
        ["pytest", "tests/", "-v"]
    ]

    for check in checks:
        result = subprocess.run(check, capture_output=True)
        assert result.returncode == 0, f"CI check failed: {check}"
```

### Property 3.2: No bare except clauses
**Validates: Requirements 1.4**

**Property**: No Python file contains `except:` without a specific exception type

**Test Strategy**: Static analysis to detect bare except
```python
def test_no_bare_except():
    """No bare except clauses should exist"""
    import ast

    for file_path in get_python_files():
        with open(file_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                assert node.type is not None, \
                    f"Bare except found in {file_path}:{node.lineno}"
```

### Property 3.3: All functions have return type annotations
**Validates: Requirements 2.5**

**Property**: Every function definition has an explicit return type annotation

**Test Strategy**: AST analysis for missing return types
```python
def test_all_functions_typed():
    """All functions must have return type annotations"""
    import ast

    for file_path in get_python_files():
        with open(file_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert node.returns is not None, \
                    f"Missing return type in {file_path}:{node.name}"
```

## Configuration

### Black Configuration (`pyproject.toml`)
```toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
```

### isort Configuration (`pyproject.toml`)
```toml
[tool.isort]
profile = "black"
line_length = 88
```

### Flake8 Configuration (`setup.cfg`)
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = .git,__pycache__,venv,node_modules
```

### MyPy Configuration (`setup.cfg`)
```ini
[mypy]
python_version = 3.11
strict = True
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

## Risk Analysis

### Risk 1: Breaking Changes from Refactoring
**Likelihood**: Medium
**Impact**: High
**Mitigation**:
- Run full test suite after each category of fixes
- Review changes carefully before committing
- Test in Docker environment matching CI

### Risk 2: Type Annotation Complexity
**Likelihood**: Medium
**Impact**: Medium
**Mitigation**:
- Start with simple type fixes
- Use `typing` module utilities (ParamSpec, Concatenate)
- Consult mypy documentation for complex cases

### Risk 3: Merge Conflicts
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- Complete fixes in single PR
- Coordinate with team on timing
- Use feature branch

## Success Criteria

1. ✅ All pre-commit hooks pass
2. ✅ CI pipeline shows all green checks
3. ✅ Zero flake8 errors
4. ✅ Zero mypy errors
5. ✅ All existing tests pass
6. ✅ Code can be merged to main branch

## Dependencies

- Docker environment with festival_app container
- Python 3.11+
- Pre-commit hooks installed
- All quality tools installed (black, isort, flake8, mypy)

## Timeline Estimate

- Phase 1 (Automated): 30 minutes
- Phase 2 (Flake8): 4-6 hours
- Phase 3 (MyPy): 4-6 hours
- Phase 4 (Verification): 1 hour
- **Total**: 10-14 hours

## Notes

- This is a one-time cleanup effort
- Future commits will be enforced by pre-commit hooks
- Team should be trained on running quality checks locally
- Consider adding quality metrics to CI dashboard
