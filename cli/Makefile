.PHONY: format lint type-check test install clean

# Format code with ruff
format:
	python src/scripts/format.py

# Just run linting without fixing
lint:
	ruff check .

# Type check with pyright
type-check:
	pyright

# Run tests
test:
	pytest

# Install the package in development mode
install:
	uv pip install -e ".[dev]"

# Clean up cache and build artifacts
clean:
	rm -rf .ruff_cache
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +

help:
	@echo "make format      - Format code with ruff"
	@echo "make lint        - Check code with ruff without fixing"
	@echo "make type-check  - Run pyright type checking"
	@echo "make test        - Run tests"
	@echo "make install     - Install package in development mode"
	@echo "make clean       - Clean up cache and build artifacts" 